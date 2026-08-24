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
from rag_store import retrieve, DOCS
from circuit_breaker import check_policy, should_escalate
from mcp_tools.actions import retry_payment, send_recovery_link, escalate_to_human


SYSTEM_PROMPT = """You are a revenue recovery agent for a payments company.

Given a failed transaction and some retrieved context docs (failure code
explanations + company policy), diagnose why it likely failed and pick ONE
recovery action:
  - retry_payment       (only for transient/technical failures)
  - send_recovery_link  (customer needs to act - new card, new session etc)
  - escalate_to_human   (nothing automated should be tried)

Each context doc below has an id in brackets, like [fc_card_declined]. In
your reasoning, cite the specific doc id(s) you relied on - don't just
describe the policy in your own words, name which doc backs your decision.
This matters for compliance auditing: we need to know exactly which policy
justified an automated action, not just a paraphrase of it.

Respond with ONLY valid JSON, nothing else, in this exact shape:
{"diagnosis": "...", "action": "retry_payment|send_recovery_link|escalate_to_human", "reasoning": "cite doc id(s) here, e.g. per [policy_consent_and_contact_limits], ..."}
"""

ACTION_FUNCS = {
    "retry_payment": retry_payment,
    "send_recovery_link": send_recovery_link,
    "escalate_to_human": escalate_to_human,
}


def get_llm():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in .env file")
    
    model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    return ChatGroq(model=model_name, api_key=api_key, temperature=0, max_tokens=400)


def diagnose_and_decide(llm, txn):
    query = f"{txn['failure_code']} {txn['failure_type']}"
    failure_docs = retrieve(query, top_k=2)

    policy_ids = {"policy_retry_limits", "policy_consent_and_contact_limits", "policy_escalation"}
    policy_docs = [d for d in DOCS if d["id"] in policy_ids]

    seen = set()
    all_docs = []
    for d in failure_docs + policy_docs:
        if d["id"] not in seen:
            seen.add(d["id"])
            all_docs.append(d)

    context_text = "\n\n".join(f"[{d['id']}] {d['text']}" for d in all_docs)

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
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
        except APIError as e:
            print(f"  groq api error: {e}, waiting 10s...")
            time.sleep(10)

    if resp is None:
        return {
            "diagnosis": "llm unavailable after retries",
            "action": "escalate_to_human",
            "reasoning": "hit groq rate limit, escalating to be safe",
        }

    raw = resp.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fixed_raw = raw
        if '"reasoning":' in fixed_raw and not fixed_raw.strip().endswith('"}'):
            reasoning_start = fixed_raw.find('"reasoning":')
            if reasoning_start != -1:
                fixed_raw = fixed_raw.strip()
                if fixed_raw.count('"') % 2 == 1:
                    fixed_raw += '"'
                if fixed_raw.count('{') > fixed_raw.count('}'):
                    fixed_raw += '}'
        
        try:
            parsed = json.loads(fixed_raw)
            print(f"  fixed incomplete JSON for txn {txn.get('id', 'unknown')}")
        except json.JSONDecodeError:
            parsed = {
                "diagnosis": "could not parse model output",
                "action": "escalate_to_human",
                "reasoning": f"json parse failed: {raw[:200]}",
            }

    return parsed


def process_transaction(llm, txn_id):
    conn = get_conn()
    txn = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    conn.close()

    if txn is None or txn["status"] != "pending":
        return None

    decision = diagnose_and_decide(llm, txn)
    proposed_action = decision["action"]

    allowed, policy_reason = check_policy(txn)

    if should_escalate(txn):
        final_action = "escalate_to_human"
        policy_reason = "max_attempts_reached, forcing escalation"
    elif not allowed:
        final_action = "escalate_to_human"
    else:
        final_action = proposed_action

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

    action_func = ACTION_FUNCS[final_action]
    result = action_func(txn_id)

    if result["outcome"] == "success":
        final_status = "resolved"
    elif final_action == "escalate_to_human":
        final_status = "escalated"
    else:
        final_status = "pending"

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
            print(f"  [{i+1}/{len(rows)}] txn {row['id']} failed: {e}")

        time.sleep(6.5)

    total_recovered = sum(r["amount_recovered"] for r in results)
    print(f"\ndone. total recovered: {total_recovered:.2f}")
    return results


if __name__ == "__main__":
    run_batch()
