from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import get_conn, init_db

app = FastAPI(title="revenue recovery agent api")

# allow the react dev server to hit this locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://ai-revenue-recovery-silk.vercel.app",
],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/stats")
def get_stats():
    conn = get_conn()

    total_at_risk = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM transactions").fetchone()["s"]
    total_recovered = conn.execute(
        "SELECT COALESCE(SUM(amount_recovered),0) as s FROM audit_log WHERE outcome='success'"
    ).fetchone()["s"]

    total_txns = conn.execute("SELECT COUNT(*) as c FROM transactions").fetchone()["c"]
    resolved = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE status='resolved'").fetchone()["c"]
    escalated = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE status='escalated'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM transactions WHERE status='pending'").fetchone()["c"]

    by_type = conn.execute(
        """SELECT failure_type,
                  COUNT(*) as total,
                  SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) as resolved_count
           FROM transactions GROUP BY failure_type"""
    ).fetchall()

    conn.close()

    recovery_rate = round((total_recovered / total_at_risk) * 100, 1) if total_at_risk else 0

    return {
        "total_at_risk": round(total_at_risk, 2),
        "total_recovered": round(total_recovered, 2),
        "recovery_rate_pct": recovery_rate,
        "total_txns": total_txns,
        "resolved": resolved,
        "escalated": escalated,
        "pending": pending,
        "by_type": [dict(r) for r in by_type],
    }


@app.get("/api/transactions")
def get_transactions():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/transactions/{txn_id}/audit")
def get_txn_audit(txn_id: int):
    conn = get_conn()
    decisions = conn.execute(
        "SELECT * FROM decisions WHERE txn_id=? ORDER BY id", (txn_id,)
    ).fetchall()
    logs = conn.execute(
        "SELECT * FROM audit_log WHERE txn_id=? ORDER BY id", (txn_id,)
    ).fetchall()
    conn.close()
    return {
        "decisions": [dict(r) for r in decisions],
        "audit_log": [dict(r) for r in logs],
    }


@app.post("/api/run-batch")
def run_batch_endpoint():
    import agent
    results = agent.run_batch()
    return {"processed": len(results), "results": results}


@app.post("/api/reset")
def reset_endpoint():
    import os
    import seed_data

    db_path = "data/recovery.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    init_db()
    seed_data.make_fake_transactions(80)
    return {"status": "reset", "transactions_created": 80}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
