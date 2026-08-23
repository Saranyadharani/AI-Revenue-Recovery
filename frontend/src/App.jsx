import { useEffect, useState } from "react";
import StatsCards from "./components/StatsCards";
import TransactionTable from "./components/TransactionTable";
import AuditDrawer from "./components/AuditDrawer";
import "./index.css";

const API_BASE = "http://localhost:8000";

function App() {
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [running, setRunning] = useState(false);

  const loadData = () => {
    fetch(`${API_BASE}/api/stats`).then((r) => r.json()).then(setStats);
    fetch(`${API_BASE}/api/transactions`).then((r) => r.json()).then(setTransactions);
  };

  useEffect(() => {
    loadData();
    // poll every 5s so the dashboard updates live while the batch runs
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRunBatch = async () => {
    setRunning(true);
    try {
      await fetch(`${API_BASE}/api/run-batch`, { method: "POST" });
    } catch (err) {
      // probably backend isn't running or groq key missing, just log it
      console.error("batch run failed:", err);
      alert("batch run failed - check that the backend is running and GROQ_API_KEY is set");
    }
    setRunning(false);
    loadData();
  };

  return (
    <div>
      <div className="topbar">
        <div className="topbar-brand">
          <div className="brand-mark"></div>
          Revenue Recovery Agent
        </div>
        <button onClick={handleRunBatch} disabled={running}>
          {running ? "running agent..." : "Run agent batch"}
        </button>
      </div>

      <div className="page">
        <StatsCards stats={stats} />
        <TransactionTable transactions={transactions} onSelect={setSelectedTxn} />
      </div>

      {selectedTxn && (
        <AuditDrawer txn={selectedTxn} onClose={() => setSelectedTxn(null)} />
      )}
    </div>
  );
}

export default App;
