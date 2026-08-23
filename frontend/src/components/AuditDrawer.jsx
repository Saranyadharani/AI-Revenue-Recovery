// slide-over panel showing the FULL audit trail for one txn - the agent's
// diagnosis, what it decided, whether the circuit breaker overrode it,
// and what actually happened when the mcp tool ran.
// this is what backs the "audit trail" requirement from the brief

import { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

export default function AuditDrawer({ txn, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!txn) return;
    setLoading(true);
    fetch(`${API_BASE}/api/transactions/${txn.id}/audit`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      });
  }, [txn]);

  if (!txn) return null;

  return (
    <div className="overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h3>{txn.txn_ref}</h3>
          <button onClick={onClose}>×</button>
        </div>

        <p style={{ fontSize: 13, color: "#64748b", marginTop: -12, marginBottom: 20 }}>
          {txn.failure_type.replace("_", " ")} · {txn.failure_code} · ₹
          {Number(txn.amount).toLocaleString("en-IN")}
        </p>

        {loading && <div className="empty-state">loading trail...</div>}

        {data && data.decisions.length === 0 && (
          <div className="empty-state">
            agent hasn't processed this transaction yet - hit "run agent batch"
          </div>
        )}

        {data &&
          data.decisions.map((d) => {
            // find the matching audit log entry, if the tool has run yet
            const outcome = data.audit_log.find((a) => a.decision_id === d.id);
            return (
              <div key={d.id}>
                <div className="trail-item">
                  <div className="trail-item-title">Agent diagnosis</div>
                  <div className="trail-item-body">{d.diagnosis}</div>
                  <div className="trail-item-meta">{new Date(d.created_at).toLocaleString()}</div>
                </div>

                <div className="trail-item">
                  <div className="trail-item-title">
                    Decision: {d.chosen_action.replace(/_/g, " ")}
                  </div>
                  <div className="trail-item-body">{d.reasoning}</div>
                  <div className="trail-item-meta">policy check: {d.policy_check}</div>
                </div>

                {outcome && (
                  <div className="trail-item">
                    <div className="trail-item-title">
                      Outcome: {outcome.outcome}
                      {outcome.amount_recovered > 0 &&
                        ` · ₹${outcome.amount_recovered.toLocaleString("en-IN")} recovered`}
                    </div>
                    <div className="trail-item-body">{outcome.notes}</div>
                    <div className="trail-item-meta">{new Date(outcome.created_at).toLocaleString()}</div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
