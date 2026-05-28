# Placement Prep Agent 🎯

> AI-powered interview prep — research any company, generate tailored questions, and chat with your own research context.

Built over 8 weeks as a **learning capstone**: each week adds one production layer — from raw API calls to a fully deployed, monitored web app.

---

## What It Does

```
You: "Prepare me for Google SDE-2, focus on DSA"
          │
          ▼
    ┌─────────────────────────────────────────────────────┐
    │  Placement Prep Agent                               │
    │                                                     │
    │  1. metadata_node   → Founded / HQ / Company type  │
    │  2. research_node   → Tavily web search (5 results)│
    │  3. synthesize_node → Gemini 160-word summary       │
    │  4. question_node   → N tailored questions          │
    │                                                     │
    │  Chat page ← grounded on your research above       │
    └─────────────────────────────────────────────────────┘
          │
          ▼
    Streamlit UI  or  terminal CLI
```

---

## Architecture

The system is split into four layers that evolved across 8 weeks of development:

```
┌──────────────────────────────────────────────────────────────────┐
│  CONVERSATION & TOOLS  (Weeks 1–2)                               │
│                                                                  │
│  day13_project.py ──evolves from──► conversation.py             │
│  day8_lcel.py     ──uses──────────► day10_tools.py              │
│                              both call ▼                         │
│                         gemini_client.py  (LLM wrapper)          │
└──────────────────────────────────────────────────────────────────┘
         │ informs                    │ feeds
         ▼                            ▼
┌──────────────────┐   ┌──────────────────────────────────────────┐
│  WEB APP          │   │  RETRIEVAL STORE  (Week 3)               │
│  (prototype)      │   │                                          │
│                  │   │  portal.py  ──serves──►  project_rag.py  │
│  app.py          │   │                          │         │      │
│  ├── index.html  │   │                      builds     queries  │
│  └── app.js      │   │                          ▼         ▼      │
│                  │   │              Ingest     ChromaDB           │
│  (Flask/Jinja    │   │              pipeline   [db_manager.py]   │
│   prototype,     │   │              chunking   Vector store      │
│   superseded     │   │                                          │
│   by Streamlit)  │   └──────────────────────────────────────────┘
└──────────────────┘              │ persists knowledge + retrieves
         │ delegates              ▼
         └──────────────────────────────────────────────────┐
                                                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  AGENTS & ORCHESTRATION  (Weeks 4–5)                            │
│                                                                  │
│              day34_35_app.py  ◄──── MAIN APP                    │
│                    │                                             │
│         coordinates│              traces│                        │
│                    ▼                    ▼                        │
│          Supervisor multi-agent   day33_langsmith.py            │
│                    │              (LangSmith tracing)            │
│          orchestrates│                                           │
│                    ▼                                             │
│          State graphs (LangGraph)                                │
│                    │                                             │
│              drives│                                             │
│                    ▼                                             │
│              ReAct agent                                         │
└──────────────────────────────────────────────────────────────────┘
         │ validated by
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  QUALITY & OPS  (Weeks 6–7)                                     │
│                                                                  │
│  day36_audit.py  (audit & validation)                           │
│       └── runs in ── tests.yml / ci.yml  (GitHub Actions)       │
└──────────────────────────────────────────────────────────────────┘
```

### LangGraph Pipeline (4-Node Core)

```
START
  │
  ▼
metadata_node ──► Tavily search ──► Gemini ──► state["metadata"]
  │
  ▼
research_node ──► Tavily search ──────────► state["research_data"]
  │
  ▼
synthesize_node ─► Gemini ───────────────► state["synthesis"]
  │
  ▼
question_node ──► Gemini ───────────────► state["questions"]
  │
  ▼
END
```

### State Schema

```python
class ResearchState(TypedDict):
    company:       str        # "Google"
    role:          str        # "SDE-2"
    focus:         str        # "DSA" | "System Design" | "Behavioral" | ...
    metadata:      dict       # {"founded": "1998", "hq": "Mountain View", "type": "Product"}
    research_data: List[str]  # raw Tavily snippets (up to 500 chars each)
    synthesis:     str        # Gemini 160-word summary
    questions:     List[str]  # formatted interview questions with [Easy/Medium/Hard]
    errors:        List[str]  # node errors captured without crashing the graph
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/placement-prep-agent
cd placement-prep-agent
pip install -r requirements.txt
```

### 2. Set API Keys

```bash
cp .env.example .env
# then open .env and fill in your keys
```

```env
GEMINI_API_KEY=your_key_here        # free at aistudio.google.com/app/apikey
TAVILY_API_KEY=your_key_here        # free at tavily.com
LANGSMITH_API_KEY=optional          # free at smith.langchain.com
```

### 3. Validate Setup

```bash
python main.py env
```

### 4. Run

**Web UI (recommended):**
```bash
python main.py ui
# Opens at http://localhost:8501
```

**Terminal research:**
```bash
python main.py research --company Google --role SDE-2 --focus DSA
python main.py research --company Flipkart --role PM --focus Behavioral --questions 3
```

**Run tests:**
```bash
python main.py test
```

**Docker:**
```bash
docker compose up
# Opens at http://localhost:8501
```

---

## How to Add a New Agent Node

Adding a new processing step to the pipeline takes **4 changes**:

**1. Add the field to `ResearchState`** (`week5/day34_35_app.py`):
```python
class ResearchState(TypedDict):
    ...
    salary_data: List[str]   # ← new field
```

**2. Write the node function:**
```python
def salary_node(state: ResearchState) -> dict:
    try:
        snippets = _search(f"{state['company']} {state['role']} salary 2025")
        return {"salary_data": snippets[:3]}
    except Exception as e:
        return {"salary_data": [], "errors": state.get("errors", []) + [str(e)]}
```

**3. Register the node and wire the edge** in `build_graph()`:
```python
b.add_node("salary_node", salary_node)
b.add_edge("question_node", "salary_node")   # insert into chain
b.add_edge("salary_node",   END)             # remove old question→END edge
```

**4. Add a test** in `week6/day38_integration_tests.py`:
```python
def test_salary_data_populated(self):
    with mock_search(), mock_gemini([...]):
        g = build_graph()
        final = run_graph(g, INIT_STATE)
        assert len(final.get("salary_data", [])) > 0
```

> **Rule:** Every node receives the full `state` dict, returns only the keys it changes. Errors go into `state["errors"]` — never raise from a node.

---

## UI Pages

| Page | What it does |
|------|-------------|
| **Research** | Company + role + focus → 4-node pipeline → summary + questions |
| **Chat** | Gemini answers grounded in your research context |
| **My Companies** | Table + detail view of all companies researched |
| **Progress** | Session metrics, readiness score (0–100), charts |
| **Settings** | API key status, model/preferences (persisted to `.pp_settings.json`) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.5 Flash |
| Web Search | Tavily API |
| Agent Framework | LangGraph (`StateGraph` + `SqliteSaver` checkpointing) |
| Orchestration | LangChain + `langchain-google-genai` |
| UI | Streamlit 1.56 |
| Vector Store | ChromaDB (Week 3 RAG) |
| Observability | LangSmith (optional) |
| Testing | pytest + `unittest.mock` |
| CI/CD | GitHub Actions |
| Deployment | Docker + Railway |

---

## Testing

```bash
# Unit tests — 21 tests, mocked APIs, runs in <2s
python -m pytest week6/day37_unit_tests.py -v

# Integration tests — 18 tests, real LangGraph, temp SQLite
python -m pytest week6/day38_integration_tests.py -v

# All tests
python -m pytest week6/ -v
```

**What's covered:**
- Graph structure (nodes, edges, count)
- Full pipeline end-to-end with mocked APIs
- Node execution order
- `SqliteSaver` checkpoint persistence across runs
- Thread isolation (separate company runs don't mix state)
- Interrupt / resume (human-in-the-loop) cycle
- State modification before resume
- Error recovery (graph completes even when search fails)

---

## Known Limitations

| Limitation | Impact | Workaround / Fix |
|------------|--------|-----------------|
| **No auth / user accounts** | All research is session-local; closing browser loses data | Add Supabase or SQLite user table |
| **Gemini rate limits** | Free tier: 15 req/min; heavy use hits 429 errors | Add Tenacity retry in `src/utils.py`; upgrade to paid tier |
| **Tavily freshness** | Search results can be weeks old for niche companies | Add `search_depth="advanced"` + date filter in `_search()` |
| **Streamlit single-thread** | Each user request blocks the others; not suitable for >5 concurrent users | Switch to FastAPI backend + React frontend |
| **No streaming output** | Gemini response appears all-at-once, not word-by-word | Use `generate_content(..., stream=True)` + `st.write_stream()` |
| **ChromaDB in-process** | Vector store runs in the same process as the UI; no sharing across workers | Switch to hosted Qdrant or Pinecone |
| **`.pp_settings.json` is local** | Settings don't follow the user across machines | Store in browser `localStorage` or a user DB |
| **No conversation memory** | Chat page has no long-term memory; each session starts fresh | Add LangGraph `MemorySaver` with a persistent thread ID per user |

---

## Environment Variables

| Variable | Required | Where to get it |
|----------|----------|----------------|
| `GEMINI_API_KEY` | ✅ | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `TAVILY_API_KEY` | ✅ | [tavily.com](https://tavily.com) |
| `LANGSMITH_API_KEY` | Optional | [smith.langchain.com](https://smith.langchain.com) |
| `LANGCHAIN_PROJECT` | Optional | Any string (default: `placement-prep-agent`) |

---

## Week-by-Week Progress

| Week | Focus | Key Files |
|------|-------|-----------|
| 1 | Claude API + Python basics | `week1/` |
| 2 | LangChain + Tavily chains | `week2/` |
| 3 | ChromaDB + RAG pipeline | `week3/` |
| 4 | LangGraph + HITL agent | `week4/` |
| 5 | Streamlit UI + LangSmith | `week5/day34_35_app.py` |
| 6 | Tests + logging + refactor | `week6/`, `src/utils.py`, `main.py` |
| 7 | Docker + GitHub Actions CI/CD | `Dockerfile`, `.github/workflows/` |
| 8 | Cloud deploy + monitoring | Railway, uptime monitoring |

---

## License

MIT — built for learning. Use freely.
