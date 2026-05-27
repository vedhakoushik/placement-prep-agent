"""
Day 36 -- Codebase Audit + Integration Map
============================================
ONE concept: understand what was built across 5 weeks before touching anything.

What this day does:
  1. Prints a file-by-file audit of every .py in the project
  2. Shows every duplication (functions defined in 3+ files)
  3. Maps the actual data flow (what calls what, what writes where)
  4. Runs one end-to-end integration test to confirm the full pipeline works
  5. Prints a hit-list for Days 37-42

No new features. No refactoring yet. Just eyes-open understanding.
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent   # placement-prep-agent/


# ================================================================
#  1. FILE INVENTORY
# ================================================================
def file_inventory():
    print("\n" + "=" * 65)
    print("  FILE INVENTORY")
    print("=" * 65)

    weeks = {
        "week1": "Claude API + Python -> Terminal Interview Coach",
        "week2": "LangChain + Tools + Tavily -> Company Research Chain",
        "week3": "Embeddings + ChromaDB + RAG -> Intelligence Store",
        "week4": "LangGraph + State + Human Loop -> ReAct Agent",
        "week5": "Multi-Agent + Streamlit + LangSmith -> Full System",
        "week6": "Integration + Testing + Docs -> Shippable Codebase",
    }

    total_files = 0
    total_lines = 0

    for week_dir, description in weeks.items():
        week_path = ROOT / week_dir
        if not week_path.exists():
            continue

        py_files = sorted(week_path.glob("*.py"))
        if not py_files:
            continue

        print(f"\n  {week_dir.upper()} -- {description}")
        week_lines = 0
        for f in py_files:
            try:
                lines = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
            except Exception:
                lines = 0
            week_lines += lines
            total_lines += lines
            total_files += 1
            print(f"    {f.name:<35} {lines:>5} lines")

        print(f"    {'-- subtotal --':<35} {week_lines:>5} lines")

    print(f"\n  {'TOTAL':<41} {total_lines:>5} lines across {total_files} files")


# ================================================================
#  2. DUPLICATION REPORT
# ================================================================
def duplication_report():
    print("\n" + "=" * 65)
    print("  DUPLICATION REPORT")
    print("  (functions defined in 2+ files = copy-paste, should be shared)")
    print("=" * 65)

    import ast, collections

    func_locations = collections.defaultdict(list)

    for py_file in ROOT.rglob("*.py"):
        if ".venv" in str(py_file) or "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            tree   = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    rel = str(py_file.relative_to(ROOT))
                    func_locations[node.name].append(rel)
        except Exception:
            continue

    duplicates = {
        name: files
        for name, files in func_locations.items()
        if len(files) >= 2 and not name.startswith("_test")
    }

    if not duplicates:
        print("\n  No duplicates found.")
        return

    # Sort by count descending
    for name, files in sorted(duplicates.items(), key=lambda x: -len(x[1])):
        print(f"\n  def {name}()  [{len(files)}x]")
        for f in files:
            print(f"    {f}")


# ================================================================
#  3. DATA FLOW MAP
# ================================================================
def data_flow_map():
    print("\n" + "=" * 65)
    print("  DATA FLOW MAP")
    print("=" * 65)

    print("""
  USER INPUT
      |
      v
  week5/day34_35_app.py   (Streamlit UI -- 3 pages)
      |
      | Research page calls stream_research()
      |   -> Tavily search (external API)
      |   -> Gemini synthesis (external API)
      |   -> writes result to st.session_state
      |
      | Chat page calls rag_answer()
      |   -> reads st.session_state (in-memory context)
      |   -> Gemini answer (external API)
      |
      | Companies page reads st.session_state.companies
      |   -> Gemini recommendation (external API)
      |
      v
  week5/day30_supervisor.py  (SupervisorAgent -- routes messages)
      |
      | route_node calls Gemini -> returns JSON {agent, company, role, ...}
      |
      |-- "research" --> ResearchAgent (search_node -> synthesize_node)
      |                      -> Tavily, Gemini
      |                      -> returns {synthesis, snippets}
      |
      |-- "question" --> QuestionAgent (generate_node)
      |                      -> Gemini
      |                      -> returns {questions}
      |
      |-- "feedback" --> FeedbackAgent (evaluate_node)
                            -> Gemini
                            -> returns {score, strengths, improvements}

  DATABASES
  ---------
  week3/qa_db/          ChromaDB -- qa_store collection
    Written by: week3/portal.py, week3/import_weeks.py
    Read by:    week3/portal.py (browse/search/flashcards)
                week3/ask.py
    NOT connected to: week4/, week5/ agents (gap to fix)

  week3/project_knowledge_db/  ChromaDB -- project_knowledge collection
    Written by: week3/project_rag.py
    Read by:    week3/import_weeks.py (migrates to qa_db)

  week4/checkpoints.db   SQLite -- LangGraph checkpoints
    Written by: week4/day27_28_persistence.py
    Read by:    week4/day27_28_persistence.py (get_state, get_state_history)

  GAPS FOUND
  ----------
  1. Week 4/5 agents DO NOT write to ChromaDB  (they should)
     -> Every research run should upsert into qa_db for RAG later
  2. Week 5 Streamlit has no ChromaDB read     (Chat page uses session only)
     -> Chat should query qa_db for cross-session context
  3. Gemini helper defined in 5 separate files  -> needs src/utils.py
  4. Tavily helper defined in 3 separate files  -> needs src/utils.py
  5. No .env validation                         -> app crashes with cryptic 401s
""")


# ================================================================
#  4. END-TO-END SMOKE TEST
#     Runs the full pipeline: Tavily -> Gemini -> result dict
#     Does NOT write to any DB (safe, read-only)
# ================================================================
def smoke_test():
    print("\n" + "=" * 65)
    print("  END-TO-END SMOKE TEST")
    print("  (Tavily search -> Gemini synthesis -> result dict)")
    print("=" * 65)

    errors = []

    # Check env vars
    for key in ["GEMINI_API_KEY", "TAVILY_API_KEY"]:
        val = os.getenv(key, "")
        status = "OK" if val else "MISSING"
        print(f"\n  {key}: {status}")
        if not val:
            errors.append(f"Missing env var: {key}")

    if errors:
        print(f"\n  Cannot run smoke test: {errors}")
        return

    # Step 1: Tavily
    print("\n  Step 1: Tavily search")
    try:
        from tavily import TavilyClient
        tavily   = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results  = tavily.search(
            query="Atlassian software engineer interview DSA",
            max_results=3, search_depth="basic"
        )
        snippets = [r.get("content", "")[:300] for r in results.get("results", []) if r.get("content")]
        print(f"  -> {len(snippets)} snippets returned")
        assert len(snippets) > 0, "Tavily returned 0 results"
        print("  -> PASS")
    except Exception as e:
        print(f"  -> FAIL: {e}")
        errors.append(str(e))
        snippets = []

    # Step 2: Gemini
    print("\n  Step 2: Gemini synthesis")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model    = genai.GenerativeModel("gemini-2.5-flash")
        block    = "\n".join(snippets[:2])
        resp     = model.generate_content(
            f"In one sentence, what is Atlassian's interview focus?\n\n{block[:1000]}"
        )
        synthesis = resp.text.strip()
        print(f"  -> {synthesis[:120]}")
        assert len(synthesis) > 10, "Gemini returned empty response"
        print("  -> PASS")
    except Exception as e:
        print(f"  -> FAIL: {e}")
        errors.append(str(e))
        synthesis = ""

    # Step 3: LangGraph import
    print("\n  Step 3: LangGraph import")
    try:
        from langgraph.graph import StateGraph, START, END
        print("  -> PASS")
    except Exception as e:
        print(f"  -> FAIL: {e}")
        errors.append(str(e))

    # Step 4: ChromaDB
    print("\n  Step 4: ChromaDB connection")
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(ROOT / "week3" / "qa_db"))
        col    = client.get_collection("qa_store")
        count  = col.count()
        print(f"  -> qa_store has {count} records")
        print("  -> PASS")
    except Exception as e:
        print(f"  -> FAIL: {e}")
        errors.append(str(e))

    # Summary
    print("\n  " + "-" * 40)
    if errors:
        print(f"  SMOKE TEST: {len(errors)} issue(s)")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  SMOKE TEST: ALL PASS")


# ================================================================
#  5. WEEK 6 HIT-LIST
# ================================================================
def hitlist():
    print("\n" + "=" * 65)
    print("  WEEK 6 HIT-LIST (what Days 37-42 will fix)")
    print("=" * 65)

    items = [
        ("Day 37", "pytest unit tests",
         "Mock Gemini + Tavily. Test nodes, routing, Pydantic models."),
        ("Day 38", "pytest integration tests",
         "Real graph runs with temp DBs. Test interrupt/resume, persistence."),
        ("Day 39", "logging + env validation",
         "Replace print() with logging. Add startup check for all env vars."),
        ("Day 40", "src/utils.py shared module",
         "Consolidate 5x _gemini(), 3x _search() into one place."),
        ("Day 41-42", "README + CLI (main.py)",
         "Full setup docs. python main.py research 'Google' 'SDE'"),
    ]

    for day, title, detail in items:
        print(f"\n  {day}: {title}")
        print(f"    {detail}")

    print("""
  GAPS TO CLOSE (discovered in data flow map):
    - Week 4/5 agents must write results to ChromaDB qa_store
    - Week 5 Chat page must query ChromaDB (not just session state)
    - All Gemini/Tavily helpers -> src/utils.py
    - .env validation before any graph runs
""")


# ================================================================
#  MAIN
# ================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("  Day 36 -- Codebase Audit + Integration Map")
    print("  No new features. Eyes-open understanding of what was built.")
    print("=" * 65)

    file_inventory()
    duplication_report()
    data_flow_map()
    smoke_test()
    hitlist()

    print("\n" + "=" * 65)
    print("  Day 36 done.")
    print("  Audit complete. Gaps documented. Hit-list ready.")
    print("  Next: Day 37 -- pytest unit tests (mock APIs, fast, free)")
    print("=" * 65)
