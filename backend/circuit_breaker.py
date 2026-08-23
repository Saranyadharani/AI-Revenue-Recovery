"""
circuit_breaker.py

this is the "stopping rules" part of the project. basic idea - dont let the
agent retry the same transaction forever, and dont let it do anything sketchy
like retry a card payment 10 times in an hour (thats how you get customers
annoyed + probably violates RBI's autopay retry guidelines for recurring pmts).

kept this dumb and simple on purpose, no fancy state machine library, just
counters + a lookup table of limits per failure type.
"""

MAX_ATTEMPTS = {
    "payment_failed": 3,
    "checkout_abandoned": 2,
    "overdue": 4,   # invoices get a bit more leeway since its not an auto-retry
}

# once we hit max attempts we stop trying automatically and hand off to a human
ESCALATE_AFTER = MAX_ATTEMPTS


def check_policy(txn):
    """
    takes a transaction row (dict-like) and decides if the agent is even
    allowed to act on it right now. returns (allowed: bool, reason: str)
    """
    failure_type = txn["failure_type"]
    attempts = txn["attempt_count"]

    limit = MAX_ATTEMPTS.get(failure_type, 3)

    if attempts >= limit:
        return False, f"max_attempts_reached ({attempts}/{limit}) - must escalate to human"

    # dumb cooldown check - dont act on something that was JUST attempted
    # (in a real system this would check actual timestamps + business hours,
    # keeping it simple here since this is a demo batch not live traffic)
    if txn["status"] == "processing":
        return False, "already_processing - skipping to avoid duplicate action"

    return True, "ok"


def should_escalate(txn):
    failure_type = txn["failure_type"]
    limit = ESCALATE_AFTER.get(failure_type, 3)
    return txn["attempt_count"] >= limit
