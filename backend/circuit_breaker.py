"""
circuit_breaker.py

this is the "stopping rules" part of the project. basic idea - dont let the
agent retry the same transaction forever, and dont let it do anything sketchy
like retry a card payment 10 times in an hour (thats how you get customers
annoyed + probably violates RBI's autopay retry guidelines for recurring pmts).

two layers of stopping rules here:
  1. max attempts per failure type (count based)
  2. minimum cooldown between attempts (time based) - this is the part that
     was missing before, attempt count alone doesn't stop the agent from
     retrying the same txn twice in the same second
"""

from datetime import datetime, timezone

MAX_ATTEMPTS = {
    "payment_failed": 3,
    "checkout_abandoned": 2,
    "overdue": 4,   # invoices get a bit more leeway since its not an auto-retry
}

# once we hit max attempts we stop trying automatically and hand off to a human
ESCALATE_AFTER = MAX_ATTEMPTS

# minimum time (minutes) that must pass since the last attempt before we'll
# try again on the same transaction - stops back-to-back retries on the same
# customer, which is the actual thing RBI-style retry guidelines care about,
# not just "how many times total"
COOLDOWN_MINUTES = {
    "payment_failed": 10,
    "checkout_abandoned": 5,
    "overdue": 1440,  # invoices: 1 day between nudges, no reason to rush these
}


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

    if txn["status"] == "processing":
        return False, "already_processing - skipping to avoid duplicate action"

    # real timestamp cooldown - not just attempt count. if the last attempt
    # was too recent, refuse regardless of how many attempts are left
    last_attempt = txn["last_attempt_at"]
    if last_attempt:
        cooldown = COOLDOWN_MINUTES.get(failure_type, 10)
        last_attempt_dt = datetime.fromisoformat(last_attempt)
        if last_attempt_dt.tzinfo is None:
            last_attempt_dt = last_attempt_dt.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - last_attempt_dt).total_seconds() / 60

        if elapsed_minutes < cooldown:
            remaining = round(cooldown - elapsed_minutes, 1)
            return False, f"cooldown_active - {remaining} min left before next attempt allowed"

    return True, "ok"


def should_escalate(txn):
    failure_type = txn["failure_type"]
    limit = ESCALATE_AFTER.get(failure_type, 3)
    return txn["attempt_count"] >= limit