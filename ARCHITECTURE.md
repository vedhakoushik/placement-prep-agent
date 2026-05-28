# Architecture Decision Record — Placement Prep Agent

---

## 1. Why LangGraph instead of a LangChain chain?

**The short answer:** chains are linear; agents are not.

A LangChain LCEL chain is a fixed sequence — `A | B | C`. Every call goes through every step in order. That is fine when the logic never branches, but interview prep is inherently conditional:

- If the company is obscure, the research node needs more Tavily results than usual.
- If the user picks "Behavioral" focus, the question node needs a different prompt than "DSA".
- The human-in-the-loop pattern (pause at `approve_node`, let the user edit the synthesis, then resume) is impossible in a pure chain — there is nowhere to save state between calls.

LangGraph solves all three problems:

| Need | Chain | LangGraph |
|------|-------|-----------|
| Conditional routing | Hard — requires custom `RunnableBranch` | Native — `add_conditional_edges()` |
| Pause and resume | Not supported | `interrupt_before=["node"]` + `SqliteSaver` |
| State that survives between steps | Manual dict passing | `TypedDict` state threaded through every node automatically |
| Error isolation per node | Chain fails completely | Each node catches its own errors, writes to `state["errors"]` |
| Observability | `LangSmith` traces chains | Same, plus per-node timing and state snapshots |

**The cost:** LangGraph adds boilerplate — you must define `StateGraph`, add every node explicitly, and wire every edge. For a single-step transformation, a chain is simpler. The graph pays off the moment you need branching, persistence, or HITL.

---

## 2. Why ChromaDB instead of SQL?

**The short answer:** interview prep data is text, not tables. SQL is optimised for exact matches; ChromaDB is optimised for semantic similarity.

When a user asks "What does Google ask about trees?", we do not want:
```sql
SELECT * FROM questions WHERE text LIKE '%trees%'
```
That misses questions about "binary search", "BFS traversal", "heap operations" — all relevant, none containing the word "trees".

ChromaDB stores each snippet as an embedding vector (a list of 768 floats that encodes *meaning*). A similarity search returns the closest vectors regardless of exact word overlap.

| Criterion | SQL (PostgreSQL) | ChromaDB |
|-----------|-----------------|---------|
| Exact keyword search | ✅ Fast | ❌ Wrong tool |
| Semantic / fuzzy search | ❌ Full-text only, no meaning | ✅ Native |
| Structured joins (user → company → session) | ✅ Perfect | ❌ Not supported |
| Setup complexity | Medium (server, schema, migrations) | Low (in-process, no server) |
| Scale | Millions of rows, easy | ~1M vectors in-process; needs managed service beyond that |
| Cost | Hosting required | Free in-process; paid for hosted |

**Where SQL still belongs:** user accounts, session history, API key storage, billing — anything relational. A production version of this app would use *both*: ChromaDB for semantic search over research snippets, PostgreSQL for everything structured.

---

## 3. How would you scale to 1,000 concurrent users?

The current stack — Streamlit + in-process LangGraph + in-process ChromaDB — would fall over at roughly 5–10 concurrent users. Streamlit runs single-threaded; one slow Gemini call blocks everyone else.

Here is the scaling path, layer by layer:

### Layer 1 — Decouple the UI from the pipeline

Replace Streamlit with **FastAPI (backend) + React (frontend)**. FastAPI is async by default — 1,000 concurrent HTTP connections are routine. The research pipeline becomes an async background job.

```
Browser → FastAPI → Celery task queue → Worker pod
                  ↑                          ↓
               Redis (job state)        Gemini + Tavily
```

### Layer 2 — Move blocking work to a task queue

Gemini calls take 2–8 seconds. At 1,000 users, serialising these destroys latency. A **Celery + Redis** queue lets each request return immediately ("your research is running, poll /status/abc123") and processes jobs in parallel across worker pods.

### Layer 3 — Externalise state

| Component | Now | At scale |
|-----------|-----|---------|
| LangGraph checkpointer | SQLite (file on disk) | PostgreSQL (`AsyncPostgresSaver`) |
| Vector store | ChromaDB in-process | Qdrant Cloud or Pinecone |
| Session cache | `st.session_state` in memory | Redis with TTL |
| Secrets | `.env` file | HashiCorp Vault or Railway Variables |

### Layer 4 — Horizontal scaling

Run multiple FastAPI + Worker pods behind a **load balancer** (Railway scales this automatically; AWS ECS or GCP Cloud Run for finer control). Because all state lives in external services (Postgres, Redis, Qdrant), any pod can handle any request — no sticky sessions needed.

### Layer 5 — Cost control

At 1,000 users, Gemini token costs become real. Add:
- **Prompt caching** — cache the Tavily snippets for a company for 24 hours; don't re-search the same company repeatedly.
- **Result caching** — if two users research Google SDE-2 DSA within the same hour, return the cached result instead of calling Gemini again.
- **Rate limiting per user** — prevent one user from exhausting the shared Gemini quota.

### Realistic capacity estimate (current stack → scaled stack)

| Stage | Concurrent users | Latency p95 |
|-------|-----------------|-------------|
| Current (Streamlit) | ~5 | 8–15s |
| FastAPI + async | ~50 | 4–8s |
| + Celery queue | ~200 | 2–5s (perceived) |
| + Horizontal pods + Redis | 1,000+ | 2–5s (perceived) |

---

## 4. What would you change with 3 more months?

Prioritised by user value, not engineering interest:

### Month 1 — Make it genuinely useful

**Streaming responses.** Right now Gemini output appears all at once after 4 seconds. Streaming makes it feel instant. `generate_content(..., stream=True)` + `st.write_stream()` is a two-hour change with an outsized UX impact.

**Persistent user accounts.** Research disappears on browser close. Add Supabase (free tier) for auth + a `companies` table. Users log in and their full history is there across devices.

**Better questions.** The current prompt asks for "3 questions". Replace with a structured Pydantic output: `List[Question]` where each question has `text`, `difficulty`, `topic`, `hint`. Render them as expandable cards in the UI.

### Month 2 — Make it production-grade

**FastAPI + React migration.** Remove the Streamlit single-thread bottleneck. This is the highest-leverage engineering change for any real user base.

**RAG over your own notes.** Let users paste their own study notes or paste a job description. Chunk and embed them into the user's personal ChromaDB collection. The chat page then retrieves from *their* knowledge, not just the Tavily web search.

**Monitoring and alerting.** Add Sentry for error tracking, Grafana for latency dashboards, PagerDuty for on-call if the error rate spikes. Without this, you are flying blind in production.

### Month 3 — Differentiate

**Mock interview mode.** Use Gemini as an interviewer: it asks a question, the user types an answer, Gemini evaluates it against ideal criteria and gives a score + feedback. This turns the tool from a research aid into an active practice partner.

**Company-specific fine-tuning data.** Scrape Glassdoor/Blind interview reports (ethically, via their APIs), embed them, and weight them higher than generic web results. Dramatically improves question quality for top-tier companies.

**Mobile app.** Export the FastAPI backend as-is; build a React Native frontend. The prep happens on the commute, not at a desk.

---

*Document last updated: Week 7 of the 8-week placement prep capstone.*
