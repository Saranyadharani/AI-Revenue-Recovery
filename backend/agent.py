"""
agent.py

the actual brains of the project. for each pending transaction:
  1. pull relevant docs from rag_store (failure reason + policy)
  2. ask the llm to diagnose + decide an action, given the docs
  3. check circuit_breaker before doing anything (this can override the llm!)
  4. write the decision to the outbox table BEFORE calling any tool
  5. call the right mcp tool
  6. log what happened to audit_log

note: step 3 is important - even if the llm says "retry", if the circuit
breaker says no more attempts, we escalate instead. the llm doesn't get to
override the safety rules, its only proposing an action.

using groq (openai/gpt-oss-120b) for the llm calls, free tier.
"""

import os
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from groq import RateLimitError, APIError

from db import get_conn, now
from rag_store import retrieve
from circuit_breaker import check_policy, should_escalate
from mcp_tools.actions import retry_payment, send_recovery_link, escalate_to_human


SYSTEM_PROMPT = """You are a revenue recovery agent for a payments company.

Given a failed transaction and some retrieved context docs (failure code
explanations + company policy), diagnose why it likely failed and pick ONE
recovery action:
  - retry_payment       (only for transient/technical failures)
  - send_recovery_link  (customer needs to act - new card, new session etc)
  - escalate_to_human   (nothing automated should be tried)

Respond with ONLY valid JSON, nothing else, in this exact shape:
{"diagnosis": "...", "action": "retry_payment|send_recovery_link|escalate_to_human", "reasoning": "..."}
"""

# tools map for calling the actual mcp action functions
ACTION_FUNCS = {
    "retry_payment": retry_payment,
    "send_recovery_link": send_recovery_link,
    "escalate_to_human": escalate_to_human,
}


def get_llm():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. add it to your .env file: "
            "GROQ_API_KEY=your_key_here"
        )
    # gpt-oss-120b is the current valid production model on groq (llama-3.3-70b
    # got fully deprecated, not just rate limited - it 404s now). free tier is
    # 8K TPM which is tight, so we cap max_tokens hard to keep each response
    # small since we only need a short json object back, not an essay
    model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    return ChatGroq(model=model_name, api_key=api_key, temperature=0, max_tokens=300)


def diagnose_and_decide(llm, txn):
    """asks the llm what to do about this one transaction, grounded in rag docs.
    retries with backoff if we hit groq's free tier rate limit instead of
    just crashing the whole batch run"""
    query = f"{txn['failure_code']} {txn['failure_type']}"
    docs = retrieve(query, top_k=3)
    context_text = "\n\n".join(d["text"] for d in docs)

    user_msg = f"""
Transaction:
  amount: {txn['amount']}
  failure_type: {txn['failure_type']}
  failure_code: {txn['failure_code']}
  previous_attempts: {txn['attempt_count']}

Relevant context:
{context_text}
"""

    max_retries = 3
    resp = None
    for attempt in range(max_retries):
        try:
            resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_msg)])
            break
        except RateLimitError:
            wait = 20 * (attempt + 1)
            print(f"  rate limited by groq, waiting {wait}s before retry...")
            time.sleep(wait)
        except APIError as e:
            # catch any other groq api error (connection issues, server errors etc)
            # so one bad call doesn't kill the whole batch run
            print(f"  groq api error: {e}, waiting 10s before retry...")
            time.sleep(10)

    if resp is None:
        # gave up after retries - escalate rather than guess
        return {
            "diagnosis": "llm unavailable after rate limit retries",
            "action": "escalate_to_human",
            "reasoning": "hit groq rate limit repeatedly, escalating to be safe",
        }

    # llms sometimes wrap json in markdown fences even when told not to, so
    # strip that out before parsing
    raw = resp.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # fallback if the model didn't behave - just escalate to be safe
        parsed = {
            "diagnosis": "could not parse model output",
            "action": "escalate_to_human",
            "reasoning": f"json parse failed, raw output was: {raw[:200]}",
        }

    return parsed


def process_transaction(llm, txn_id):
    """runs the full pipeline for one transaction. this is the function
    that gets called in a loop over the whole batch"""
    conn = get_conn()
    txn = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    conn.close()

    if txn is None:
        return None

    if txn["status"] not in ("pending",):
        return None  # skip stuff thats already resolved/escalated

    # step 1+2: get llm's proposed diagnosis + action
    decision = diagnose_and_decide(llm, txn)
    proposed_action = decision["action"]

    # step 3: circuit breaker gets final say, not the llm
    allowed, policy_reason = check_policy(txn)

    if should_escalate(txn):
        final_action = "escalate_to_human"
        policy_reason = "max_attempts_reached, forcing escalation regardless of llm choice"
    elif not allowed:
        final_action = "escalate_to_human"
    else:
        final_action = proposed_action

    # step 4: write to outbox BEFORE calling any tool - this is the important part,
    # we want a record of the decision even if the tool call below fails/crashes
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO decisions (txn_id, diagnosis, chosen_action, reasoning, policy_check, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (txn_id, decision["diagnosis"], final_action, decision["reasoning"], policy_reason, now()),
    )
    decision_id = cur.lastrowid
    conn.execute("UPDATE transactions SET status='processing' WHERE id=?", (txn_id,))
    conn.commit()
    conn.close()

    # step 5: actually call the tool - this is local/simulated logic, no
    # api call here so no rate limit risk (that's handled in diagnose_and_decide)
    action_func = ACTION_FUNCS[final_action]
    result = action_func(txn_id)

    # step 6: audit log. status comes from what ACTUALLY happened (result),
    # not from which action was chosen - a failed retry should stay pending
    # so it can be picked up again, not get marked resolved
    if result["outcome"] == "success":
        final_status = "resolved"
    elif final_action == "escalate_to_human":
        final_status = "escalated"
    else:
        final_status = "pending"  # failed attempt, stays pending for another try

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO audit_log (txn_id, decision_id, action, outcome, amount_recovered, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            txn_id,
            decision_id,
            final_action,
            result["outcome"],
            result.get("amount_recovered", 0),
            result.get("notes", ""),
            now(),
        ),
    )
    cur.execute("UPDATE transactions SET status=? WHERE id=?", (final_status, txn_id))
    conn.commit()
    conn.close()

    return {
        "txn_id": txn_id,
        "action": final_action,
        "outcome": result["outcome"],
        "amount_recovered": result.get("amount_recovered", 0),
    }


def run_batch(limit=None):
    """runs the agent over every pending transaction. this is what gives us
    the 'measured money recovered across a batch' metric for the pitch"""
    llm = get_llm()

    conn = get_conn()
    rows = conn.execute("SELECT id FROM transactions WHERE status='pending'").fetchall()
    conn.close()

    if limit:
        rows = rows[:limit]

    print(f"processing {len(rows)} pending transactions...")
    results = []
    for i, row in enumerate(rows):
        try:
            res = process_transaction(llm, row["id"])
            if res:
                results.append(res)
                print(f"  [{i+1}/{len(rows)}] txn {res['txn_id']}: {res['action']} -> {res['outcome']}")
        except Exception as e:
            # don't let one bad transaction kill the entire batch - log it
            # and move on, this transaction just stays pending for next run
            print(f"  [{i+1}/{len(rows)}] txn {row['id']} failed with error: {e}")

        # groq's free tier is 8K tokens/min for gpt-oss-120b, which is the
        # actual binding constraint here (not the 30 req/min limit). each
        # call is roughly ~700-750 tokens now that max_tokens is capped, so
        # ~6.5s spacing keeps us comfortably under 8K TPM
        time.sleep(6.5)

    total_recovered = sum(r["amount_recovered"] for r in results)
    print(f"\ndone. total recovered so far: {total_recovered:.2f}")
    return results


if __name__ == "__main__":
    run_batch()