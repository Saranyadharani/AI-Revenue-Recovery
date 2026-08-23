# Revenue Recovery Agent

Built for the **Razorpay AI Buildathon 2026** — AI Revenue Recovery track.

An agent that finds revenue slipping away — failed payments, abandoned
checkouts, overdue invoices — diagnoses why, and takes a bounded,
policy-safe recovery action. Every decision is logged before it's acted on,
and a circuit breaker enforces hard stopping rules so the agent can never
retry indefinitely or act outside policy.

**Live demo:** [ai-revenue-recovery-silk.vercel.app](https://ai-revenue-recovery-silk.vercel.app)

> Note: the backend runs on Render's free tier, which spins down after ~15
> minutes idle. The first request after a gap can take 30–60s to wake up —
> that's a cold start, not a bug.

---

## Architecture

<img width="2967" height="1274" alt="architecture diagram" src="https://github.com/user-attachments/assets/a46f97a5-5b82-4601-8295-747d2038283f" />

Full breakdown of every design decision, including which parts are modeled
on Razorpay's own public engineering patterns (event-driven processing,
outbox pattern, circuit breakers) and why SQLite was chosen over
Kafka/Postgres/Redis for this build, is in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## What's real vs simulated

- **MCP server and tools** — real, using the official `mcp` Python SDK
- **LangChain agent** — real, calls a real LLM (Groq) for every diagnosis
- **RAG retrieval** — real but simplified: keyword-overlap retrieval over a
  small curated (~15 doc) knowledge base instead of embeddings, since the
  doc set is intentionally small. Swapping in a vector store
  (Chroma/FAISS) is the natural next step for a larger knowledge base.
- **Payment retry / recovery link / bank interactions** — simulated, with
  randomized success rates. This isn't wired to a real payment gateway or
  SMS/email provider — it's a demo of the decision-making and safety layers,
  not a production payments integration.

## Tech stack

| Layer | Tech |
|---|---|
| Agent orchestration | LangChain |
| LLM | Groq (`openai/gpt-oss-120b`) |
| Tool layer | MCP (Model Context Protocol) — official Python SDK |
| Backend API | FastAPI |
| Database | SQLite (outbox pattern: `transactions`, `decisions`, `audit_log`) |
| Frontend | React + Vite |
| Deployment | Backend on Render (Docker), frontend on Vercel |

## Project structure

```
backend/
  db.py                  - sqlite schema: transactions, decisions (outbox), audit_log
  seed_data.py             - generates fake failed transactions for the demo
  rag_store.py              - failure-reason + policy docs, keyword retrieval
  circuit_breaker.py         - stopping rules (max retries, cooldowns)
  agent.py                    - the langchain agent, ties everything together
  mcp_tools/
    actions.py                  - retry/recovery-link/escalate logic (simulated)
    server.py                    - real mcp server exposing those as tools
  main.py                        - fastapi app (dashboard api + agent trigger)
  requirements.txt
frontend/
  src/
    App.jsx                        - main dashboard
    components/
      StatsCards.jsx                   - headline recovery metrics
      TransactionTable.jsx              - transaction list
      AuditDrawer.jsx                    - click-through audit trail
docs/
  ARCHITECTURE.md                          - full design writeup + requirement mapping
  LEARNINGS.md                              - what broke and how it got fixed, as it happened

"""

## Known limitations / next steps

- Circuit breaker cooldowns are attempt-count based, not real timestamp
  cooldowns — would need a scheduler for genuine time-based rate limiting
- No auth on the dashboard — fine for a demo, not for production
- Batch run is synchronous and paced to stay under Groq's free-tier rate
  limits (~8K tokens/min on `gpt-oss-120b`), so a full 80-transaction batch
  takes several minutes. A background job queue would remove this
  constraint at higher volume or on a paid tier
- RAG retrieval is keyword-based, not embedding-based — fine at ~15 docs,
  wouldn't scale to a large knowledge base as-is

See **[docs/LEARNINGS.md](docs/LEARNINGS.md)** for the full list of things
that broke during development and how each was actually fixed — including a
deprecated model that returned a confusing 404, a Groq token-per-minute
limit that looked like a request-rate problem at first, and a Vercel build
that silently kept serving a stale deployment after a syntax error.
