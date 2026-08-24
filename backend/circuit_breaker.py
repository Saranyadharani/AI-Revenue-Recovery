from datetime import datetime, timezone

MAX_ATTEMPTS = {
    "payment_failed": 3,
    "checkout_abandoned": 2,
    "overdue": 4,   # invoices get a bit more leeway since its not an auto-retry
}

# once it hit max attempts it stop trying automatically and hand off to a human
ESCALATE_AFTER = MAX_ATTEMPTS

# minimum time (minutes) that must pass since the last attempt before we'll
# try again on the same transaction - stops back-to-back retries on the same
# customer, which is the actual thing RBI-style retry guidelines care about
COOLDOWN_MINUTES = {
    "payment_failed": 10,
    "checkout_abandoned": 5,
    "overdue": 1440,  
}


def check_policy(txn):
    failure_type = txn["failure_type"]
    attempts = txn["attempt_count"]

    limit = MAX_ATTEMPTS.get(failure_type, 3)

    if attempts >= limit:
        return False, f"max_attempts_reached ({attempts}/{limit}) - must escalate to human"

    if txn["status"] == "processing":
        return False, "already_processing - skipping to avoid duplicate action"

    # real timestamp cooldown - not just attempt count. if the last attempt was too recent, refuse regardless of how many attempts are left
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
