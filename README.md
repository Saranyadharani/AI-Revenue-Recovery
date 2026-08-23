# AI Revenue Recovery Agent

built for the razorpay ai buildathon 2026 - AI Revenue Recovery track.

an agent that looks at failed payments, abandoned checkouts, and overdue
invoices, figures out why they failed using RAG over failure-code + policy
docs, then decides on a recovery action through MCP tools - bounded by
stopping rules (circuit breaker) so it can't retry forever or act outside
policy. every decision gets written to an outbox table before any action
fires, so there's a full audit trail even if something crashes mid-flow.

## architecture

payment/checkout events -> RAG store (failure docs + policy) -> LangChain
agent (diagnoses + proposes action) -> circuit breaker (final say on
whether action is allowed) -> outbox write (decision logged) -> MCP tool
call (retry / recovery link / escalate) -> audit log -> dashboard

modeled loosely on patterns razorpay themselves have written about publicly
(event-driven processing, outbox pattern for reliability, circuit breakers).
used sqlite instead of kafka/postgres/redis since this is a solo 2-week
hackathon build, not production infra - see LEARNINGS.md for that tradeoff.

## setup

### backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# get a free groq api key at console.groq.com, no card needed
export GROQ_API_KEY=your_key_here

python3 seed_data.py     # generates 80 fake failed transactions
python3 main.py           # starts the api on localhost:8000
```

### frontend

```bash
cd frontend
npm install
npm run dev                # starts on localhost:5173
```

Open localhost:5173, click "Run agent batch" to process all pending
transactions. Click any row for the full audit trail.

## project structure

```
backend/
  db.py              - sqlite schema (transactions, decisions/outbox, audit_log)
  seed_data.py        - generates fake failed transactions
  rag_store.py         - failure-reason + policy docs, keyword retrieval
  circuit_breaker.py   - stopping rules (max retries, cooldowns)
  agent.py              - langchain agent, ties everything together
  mcp_tools/
    actions.py           - the actual retry/recovery-link/escalate logic (simulated)
    server.py             - mcp server exposing those as tools
  main.py                 - fastapi dashboard api
frontend/
  src/
    App.jsx                - main dashboard
    components/
      StatsCards.jsx          - headline recovery metrics
      TransactionTable.jsx     - transaction list
      AuditDrawer.jsx           - click-through audit trail
```

## what's simulated vs real

- MCP server and tools: real, using the official python mcp sdk
- LangChain agent: real, calls a real llm (groq/llama-3.3-70b)
- RAG retrieval: real but simplified - keyword overlap instead of embeddings,
  since the doc set is small (~15 docs). would swap for a proper vector store
  (chroma/faiss) if scaling to a larger knowledge base.
- Payment retry / recovery link / bank interactions: simulated with random
  success rates, since this is a demo and not actually wired to a real
  payment gateway or sms/email provider.

## known limitations / next steps

- circuit breaker cooldowns are attempt-count based, not real timestamp-based
  cooldowns (would need a scheduler for that)
- no auth on the dashboard, fine for a demo not for production
- batch run is synchronous/blocking - fine for ~80 txns, would need a
  background job queue for a bigger batch
