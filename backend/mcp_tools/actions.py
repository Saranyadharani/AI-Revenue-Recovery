"""
actions.py

the actual "business logic" for our 3 recovery actions. kept separate from
the mcp server wiring so i can unit test these without spinning up mcp stuff.

these are FAKE for the demo - not actually calling razorpay's api or sending
real sms/email. just simulating success/fail so we can measure a recovery
rate on the batch. would be a simple swap to real api calls later.
"""

import random
from db import get_conn, now

random.seed(7)


def retry_payment(txn_id: int) -> dict:
    """simulates retrying a failed payment. success chance depends a bit on
    failure type since some failures are more 'retryable' than others"""
    conn = get_conn()
    txn = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()

    if txn is None:
        conn.close()
        return {"outcome": "failed", "notes": "txn not found"}

    # bank_server_down / otp_timeout / issuer_unavailable are usually transient,
    # so give those a better success chance than something like card_declined
    transient_codes = {"bank_server_down", "otp_timeout", "issuer_unavailable"}
    success_chance = 0.65 if txn["failure_code"] in transient_codes else 0.35

    succeeded = random.random() < success_chance
    recovered = txn["amount"] if succeeded else 0

    conn.execute(
        "UPDATE transactions SET attempt_count = attempt_count + 1, "
        "status = ?, last_attempt_at = ? WHERE id = ?",
        ("resolved" if succeeded else "pending", now(), txn_id),
    )
    conn.commit()
    conn.close()

    return {
        "outcome": "success" if succeeded else "failed",
        "amount_recovered": recovered,
        "notes": f"retry attempt on {txn['failure_code']}",
    }


def send_recovery_link(txn_id: int) -> dict:
    """simulates sending a payment link via sms/email. slightly better odds
    than a blind retry since we're giving the customer a fresh path to pay"""
    conn = get_conn()
    txn = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()

    if txn is None:
        conn.close()
        return {"outcome": "failed", "notes": "txn not found"}

    succeeded = random.random() < 0.45
    recovered = txn["amount"] if succeeded else 0

    conn.execute(
        "UPDATE transactions SET attempt_count = attempt_count + 1, "
        "status = ?, last_attempt_at = ? WHERE id = ?",
        ("resolved" if succeeded else "pending", now(), txn_id),
    )
    conn.commit()
    conn.close()

    return {
        "outcome": "success" if succeeded else "failed",
        "amount_recovered": recovered,
        "notes": "recovery link sent",
    }


def escalate_to_human(txn_id: int) -> dict:
    """no randomness here, this always 'succeeds' in the sense that its
    handed off properly. money isn't recovered by the agent at this point"""
    conn = get_conn()
    conn.execute(
        "UPDATE transactions SET status='escalated', last_attempt_at=? WHERE id=?",
        (now(), txn_id),
    )
    conn.commit()
    conn.close()

    return {
        "outcome": "escalated",
        "amount_recovered": 0,
        "notes": "handed off to human collections/support agent",
    }
