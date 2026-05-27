"""
Day 27-28 -- SqliteSaver Persistence + compare_companies()
============================================================
ONE concept: checkpoints written to disk survive process restarts.

What is NEW today vs Day 26:
  1. SqliteSaver   -- writes checkpoints to a .db file on disk
                      (MemorySaver from Day 26 dies when the process exits)
  2. thread_id     -- each company gets its own thread in the same .db
  3. graph.get_state(config)  -- reads ANY thread's saved state from disk
  4. compare_companies()      -- pulls 2 threads and shows a side-by-side table

The graph is identical to Day 24 (no interrupt -- keep it focused).
The nodes are the same. The ONLY new thing is persistence.

Run this file TWICE to see the point:
  First run  -- writes 2 company states to disk
  Second run -- reads them back, shows comparison table,
                then overwrites Google with a fresh run (shows update works)

Requirements:
  pip install langgraph-checkpoint-sqlite   (likely already installed)
"""

import os, re, sqlite3
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "week4/checkpoints.db"


# ── State (same as Day 24) ────────────────────────────────────────────────────
class PlacementState(TypedDict):
    company:       str
    role:          str
    metadata:      dict
    research_data: List[str]
    focus:         str
    synthesis:     str
    questions:     List[str]
    errors:        List[str]


# ── Nodes (same pipeline as Day 24, no changes) ───────────────────────────────
def metadata_node(state: PlacementState) -> dict:
    print(f"  [metadata] {state['company']}", end="", flush=True)
    try:
        from tavily import TavilyClient
        import google.generativeai as genai
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model  = genai.GenerativeModel("gemini-2.5-flash")
        res    = tavily.search(
            query=f"{state['company']} company founded headquarters",
            max_results=2, search_depth="basic"
        )
        content = " ".join(r.get("content", "") for r in res.get("results", []))
        resp    = model.generate_content(
            f"From text about {state['company']}, reply EXACTLY:\n"
            "Founded: <>\nHQ: <>\nType: <>\n\n"
            f"Text: {content[:1500]}"
        )
        meta = {"founded": "?", "hq": "?", "type": "?"}
        for line in resp.text.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                if k in meta:
                    meta[k] = v.strip()
        print(f" -> HQ={meta['hq']}")
        return {"metadata": meta}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"metadata": {}, "errors": state.get("errors", []) + [str(e)]}


def research_node(state: PlacementState) -> dict:
    print(f"  [research]  {state['company']}", end="", flush=True)
    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res    = tavily.search(
            query=f"{state['company']} {state['role']} interview 2024 2025",
            max_results=5, search_depth="basic"
        )
        snippets = [
            r.get("content", "")[:500]
            for r in res.get("results", [])
            if r.get("content", "").strip()
        ]
        print(f" -> {len(snippets)} snippets")
        return {"research_data": snippets}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"research_data": [], "errors": state.get("errors", []) + [str(e)]}



def synthesize_node(state: PlacementState) -> dict:
    print(f"  [synthesize] focus={state.get('focus','DSA')}", end="", flush=True)
    if not state.get("research_data"):
        return {"synthesis": "No data."}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model  = genai.GenerativeModel("gemini-2.5-flash")
        block  = "\n---\n".join(state["research_data"])
        resp   = model.generate_content(
            f"Summarize {state['company']} {state['role']} interview for "
            f"{state.get('focus','DSA')} focus. 120 words max.\n\n{block[:3000]}"
        )
        s = resp.text.strip()
        print(f" -> {len(s)} chars")
        return {"synthesis": s}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"synthesis": "failed", "errors": state.get("errors", []) + [str(e)]}


def question_node(state: PlacementState) -> dict:
    focus = state.get("focus", "DSA")
    print(f"  [questions] {focus}", end="", flush=True)
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp  = model.generate_content(
            f"3 {focus} questions for {state['company']} {state['role']}. "
            f"Q1-Q3 with [Easy/Medium/Hard]. Context:\n{state.get('synthesis','')[:300]}"
        )
        parts = re.split(r"\n(?=Q\d+\.)", resp.text.strip())
        qs    = [p.strip() for p in parts if p.strip()] or [resp.text.strip()]
        print(f" -> {len(qs)} questions")
        return {"questions": qs}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"questions": [], "errors": state.get("errors", []) + [str(e)]}



# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph(checkpointer):
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(PlacementState)
    builder.add_node("metadata_node",   metadata_node)
    builder.add_node("research_node",   research_node)
    builder.add_node("synthesize_node", synthesize_node)
    builder.add_node("question_node",   question_node)

    # Straight line -- same as Day 23, but compiled WITH a checkpointer
    builder.add_edge(START,              "metadata_node")
    builder.add_edge("metadata_node",    "research_node")
    builder.add_edge("research_node",    "synthesize_node")
    builder.add_edge("synthesize_node",  "question_node")
    builder.add_edge("question_node",    END)

    return builder.compile(checkpointer=checkpointer)


# ── Run one company ───────────────────────────────────────────────────────────
def run_company(graph, company: str, role: str, focus: str) -> str:
    """Runs the graph for one company. Returns the thread_id used."""
    # thread_id is what separates companies in the checkpoint store
    thread_id = f"{company.lower().replace(' ', '_')}"
    config    = {"configurable": {"thread_id": thread_id}}

    print(f"\n  {company} | {role} | {focus} | thread={thread_id!r}")

    initial: PlacementState = {
        "company":       company,
        "role":          role,
        "metadata":      {},
        "research_data": [],
        "focus":         focus,
        "synthesis":     "",
        "questions":     [],
        "errors":        [],
    }

    try:
        for _ in graph.stream(initial, config=config, stream_mode="values"):
            pass   # we only need the side effect: writing to checkpointer
    except Exception as e:
        print(f"  ERROR: {e}")

    return thread_id


# ── compare_companies() ───────────────────────────────────────────────────────
def compare_companies(graph, thread_ids: list):
    """
    Reads each thread's SAVED STATE from disk and prints a comparison table.
    This is the Day 27-28 payload: data persisted from a previous run,
    retrieved with graph.get_state(config).
    """
    print("\n" + "=" * 65)
    print("  COMPANY COMPARISON (reading from disk)")
    print("=" * 65)
    print(f"\n  {'Company':<16} {'Focus':<15} {'HQ':<22} {'Snippets':<10} {'Q#'}")
    print(f"  {'-'*16} {'-'*15} {'-'*22} {'-'*10} {'-'*4}")

    for tid in thread_ids:
        config   = {"configurable": {"thread_id": tid}}
        snapshot = graph.get_state(config)
        if not snapshot or not snapshot.values:
            print(f"  {tid:<16} -- no saved state --")
            continue
        v = snapshot.values
        print(
            f"  {v.get('company','?'):<16} "
            f"{v.get('focus','?'):<15} "
            f"{v.get('metadata',{}).get('hq','?')[:22]:<22} "
            f"{len(v.get('research_data',[])):<10} "
            f"{len(v.get('questions',[]))}"
        )

    print()
    for tid in thread_ids:
        config   = {"configurable": {"thread_id": tid}}
        snapshot = graph.get_state(config)
        if snapshot and snapshot.values:
            v = snapshot.values
            syn = v.get("synthesis", "")
            if syn and syn not in ("No data.", "failed"):
                print(f"  [{v.get('company')}] {syn[:120]}")
                print()
    print("=" * 65)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Setup SqliteSaver ──────────────────────────────────────────────────────
    checkpointer = None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        os.makedirs("week4", exist_ok=True)
        conn         = sqlite3.connect(DB_PATH, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        print(f"\nUsing SqliteSaver -> {DB_PATH}")
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        print("\nUsing MemorySaver (SqliteSaver unavailable)")

    print("=" * 60)
    print("  Day 27-28 -- Persistence + compare_companies()")
    print("  NEW: SqliteSaver writes to disk | get_state() reads back")
    print("=" * 60)

    graph = build_graph(checkpointer)

    # ── Run 2 companies (keeps API calls under the free quota) ────────────────
    print("\n  Running 2 companies (each gets its own thread in the .db)...")

    t1 = run_company(graph, "Google",    "Software Engineer",        "DSA")
    t2 = run_company(graph, "Microsoft", "Software Engineer",        "System Design")

    # ── Compare from disk ─────────────────────────────────────────────────────
    compare_companies(graph, [t1, t2])

    # ── Show checkpoint history for one thread ─────────────────────────────────
    print("  Checkpoint history for Google thread:")
    try:
        history = list(graph.get_state_history({"configurable": {"thread_id": t1}}))
        print(f"  {len(history)} snapshots saved (one per node transition)\n")
        for i, snap in enumerate(history[:5]):
            step = snap.metadata.get("step", i)
            keys = [k for k in (snap.values or {}).keys()][:4]
            print(f"    snapshot {i}: step={step} | keys={keys}")
    except Exception as e:
        print(f"  get_state_history: {e}")

    # ── Retrieve one company's full state ──────────────────────────────────────
    print(f"\n  Retrieving Google's saved state from disk...")
    snap = graph.get_state({"configurable": {"thread_id": t1}})
    if snap and snap.values:
        v = snap.values
        print(f"  company   : {v.get('company')}")
        print(f"  metadata  : {v.get('metadata')}")
        print(f"  snippets  : {len(v.get('research_data',[]))}")
        print(f"  questions : {len(v.get('questions',[]))}")
        if v.get("questions"):
            print(f"\n  First question:\n  {v['questions'][0][:200]}")


