"""
seed_data.py - generates fake failed transactions so we have something to
run the agent on. numbers are made up but the failure codes are based on
real razorpay/payment gateway error codes i found online.
"""

import random
import os
from db import get_conn, init_db, now

random.seed(42)  # keeping this fixed so results are reproducible for the demo

FAILURE_TYPES = {
    "payment_failed": [
        "insufficient_funds",
        "card_declined",
        "bank_server_down",
        "expired_card",
        "otp_timeout",
        "issuer_unavailable",
    ],
    "checkout_abandoned": [
        "cart_left_at_payment",
        "cart_left_at_otp",
        "session_timeout",
    ],
    "overdue": [
        "invoice_overdue_7d",
        "invoice_overdue_15d",
        "invoice_overdue_30d",
    ],
}

CUSTOMER_PREFIX = ["cust", "usr", "biz"]


def reset_database():
    """Delete existing database to start fresh"""
    db_path = "data/recovery.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database")


def make_fake_transactions(n=80):
    conn = get_conn()
    cur = conn.cursor()

    for i in range(n):
        failure_type = random.choices(
            list(FAILURE_TYPES.keys()), weights=[0.55, 0.25, 0.20]
        )[0]
        failure_code = random.choice(FAILURE_TYPES[failure_type])

        amount = round(random.uniform(299, 45000), 2)
        customer_id = f"{random.choice(CUSTOMER_PREFIX)}_{1000+i}"
        txn_ref = f"txn_{random.randint(100000,999999)}"

        cur.execute(
            """INSERT INTO transactions
               (txn_ref, customer_id, amount, failure_type, failure_code, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (txn_ref, customer_id, amount, failure_type, failure_code, now()),
        )

    conn.commit()
    conn.close()
    print(f"Inserted {n} fake transactions")


if __name__ == "__main__":
    reset_database()
    init_db()
    make_fake_transactions(80)