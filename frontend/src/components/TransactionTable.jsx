export default function TransactionTable({ transactions, onSelect }) {
  const fmtMoney = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

  if (!transactions.length) {
    return (
      <div className="card">
        <div className="card-header">Transactions</div>
        <div className="empty-state">
          no transactions yet - run the seed script first (python seed_data.py)
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">Transactions ({transactions.length})</div>
      <table>
        <thead>
          <tr>
            <th>Txn ref</th>
            <th>Customer</th>
            <th>Amount</th>
            <th>Failure type</th>
            <th>Code</th>
            <th>Attempts</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((txn) => (
            <tr key={txn.id} className="clickable" onClick={() => onSelect(txn)}>
              <td className="mono">{txn.txn_ref}</td>
              <td>{txn.customer_id}</td>
              <td className="mono">{fmtMoney(txn.amount)}</td>
              <td>{txn.failure_type.replace("_", " ")}</td>
              <td className="mono">{txn.failure_code}</td>
              <td>{txn.attempt_count}</td>
              <td>
                <span className={`badge ${txn.status}`}>{txn.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
