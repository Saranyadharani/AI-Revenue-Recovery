export default function StatsCards({ stats }) {
  if (!stats) return null;

  const fmtMoney = (n) =>
    "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });

  return (
    <div className="stats-row">
      <div className="stat-card">
        <div className="stat-label">Total at risk</div>
        <div className="stat-value">{fmtMoney(stats.total_at_risk)}</div>
        <div className="stat-sub">{stats.total_txns} transactions</div>
      </div>

      <div className="stat-card highlight">
        <div className="stat-label">Recovered</div>
        <div className="stat-value">{fmtMoney(stats.total_recovered)}</div>
        <div className="stat-sub">{stats.recovery_rate_pct}% recovery rate</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Resolved</div>
        <div className="stat-value">{stats.resolved}</div>
        <div className="stat-sub">auto-recovered by agent</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Escalated</div>
        <div className="stat-value">{stats.escalated}</div>
        <div className="stat-sub">handed to human</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Pending</div>
        <div className="stat-value">{stats.pending}</div>
        <div className="stat-sub">not yet processed</div>
      </div>
    </div>
  );
}
