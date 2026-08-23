"""
using sqlite instead of postgres/redis for demo
It follows the same idea as an event queue + outbox pattern, I  just simplified it to one file.
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "recovery.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # this table is basically our "event stream" - every failed txn/abandoned checkout
    # lands here with status = pending, then the agent picks it up
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_ref TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            failure_type TEXT NOT NULL,      -- payment_failed / checkout_abandoned / overdue
            failure_code TEXT,               -- e.g. insufficient_funds, card_declined etc
            status TEXT DEFAULT 'pending',   -- pending -> processing -> resolved / escalated
            attempt_count INTEGER DEFAULT 0,
            created_at TEXT,
            last_attempt_at TEXT
        )
    """)

    # outbox table - agent writes its decision + reasoning HERE first, before any
    # mcp tool actually fires. so even if a tool call crashes we still have a record
    # of what the agent decided and why
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id INTEGER NOT NULL,
            diagnosis TEXT,
            chosen_action TEXT,     -- retry_payment / send_recovery_link / escalate_to_human
            reasoning TEXT,
            policy_check TEXT,      -- did it pass circuit breaker rules or not
            created_at TEXT,
            FOREIGN KEY(txn_id) REFERENCES transactions(id)
        )
    """)

    # audit trail - what actually happened after the tool ran
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id INTEGER NOT NULL,
            decision_id INTEGER,
            action TEXT,
            outcome TEXT,           -- success / failed / skipped_by_policy
            amount_recovered REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY(txn_id) REFERENCES transactions(id)
        )
    """)

    conn.commit()
    conn.close()
    print("db initialized at", DB_PATH)


def now():
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    init_db()