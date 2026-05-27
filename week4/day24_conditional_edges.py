"""
Day 24 -- Conditional Edges + Retry Loop
==========================================
ONE concept: replace a fixed edge with a router function.

What is NEW today vs Day 23:
  1. `retry_count` added to state  (needed so the router can count attempts)
  2. `error_node`                  (terminal node for exhausted retries)
  3. `route_after_research()`      (router function -- returns a branch name)
  4. `add_conditional_edges()`     (replaces the fixed research->synthesize edge)

Everything else (nodes, compile, stream) is the same as Day 23.

Graph:
  START -> metadata_node -> research_node -> [router]
                                  ^               |-- "enough"  -> synthesize_node
                                  |               |-- "retry"   -> research_node  (loop back)
                                  |_______________|-- "error"   -> error_node -> END
                                                       (retry_count >= 3)
           synthesize_node -> question_node -> END

How the demo forces a retry:
  The router needs MIN_SNIPPETS to move forward. The first search uses
  max_results=1 intentionally (labelled clearly below as DEMO_FIRST_CALL).
  This simulates what happens when Tavily returns insufficient data in production.
  The retry call uses max_results=5.
"""

import os, re
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()

# ── Demo config ────────────────────────────────────────────────────────────────
MIN_SNIPPETS      = 3   # router needs at least this many snippets to proceed
MAX_RETRIES       = 3   # after this many attempts, route to error_node
DEMO_FIRST_CALL   = 1   # max_results on attempt #1 (forces a retry in the demo)
NORMAL_CALL       = 5   # max_results on attempts #2+


# ── State  (Day 23 fields + retry_count) ──────────────────────────────────────
class PlacementState(TypedDict):
    company:       str
    role:          str
    metadata:      dict
    research_data: List[str]
    retry_count:   int          # NEW today: tracks how many times research ran
    focus:         str
    synthesis:     str
    questions:     List[str]
    errors:        List[str]


# ── Nodes ─────────────────────────────────────────────────────────────────────
def metadata_node(state: PlacementState) -> dict:
    print(f"\n[metadata_node] {state['company']}")
    try:
        from tavily import TavilyClient
        import google.generativeai as genai
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model  = genai.GenerativeModel("gemini-2.5-flash")
        res    = tavily.search(
            query=f"{state['company']} company founded headquarters size",
            max_results=2, search_depth="basic"
        )
        content = " ".join(r.get("content", "") for r in res.get("results", []))
        resp    = model.generate_content(
            f"From text about {state['company']}, reply EXACTLY:\n"
            "Founded: <>\nHQ: <>\nSize: <>\nType: <>\n\n"
            f"Text: {content[:1500]}"
        )
        meta = {"founded": "?", "hq": "?", "size": "?", "type": "?"}
        for line in resp.text.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                if k in meta:
                    meta[k] = v.strip()
        print(f"  -> HQ={meta['hq']} | Type={meta['type']}")
        return {"metadata": meta}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"metadata": {}, "errors": state.get("errors", []) + [str(e)]}


def research_node(state: PlacementState) -> dict:
    """
    Searches for interview data.
    Attempt #1: max_results=DEMO_FIRST_CALL (1) -- simulates insufficient data.
    Attempt #2+: max_results=NORMAL_CALL (5)   -- enough to pass the router.
    """
    count = state.get("retry_count", 0)
    max_r = DEMO_FIRST_CALL if count == 0 else NORMAL_CALL
    print(f"\n[research_node] attempt={count + 1} | max_results={max_r}")

    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res    = tavily.search(
            query=f"{state['company']} {state['role']} interview experience 2024 2025",
            max_results=max_r, search_depth="basic"
        )
        snippets = [
            r.get("content", "")[:500]
            for r in res.get("results", [])
            if r.get("content", "").strip()
        ]
        print(f"  -> got {len(snippets)} snippets")
        return {"research_data": snippets, "retry_count": count + 1}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "research_data": [],
            "retry_count":   count + 1,
            "errors":        state.get("errors", []) + [str(e)],
        }


def synthesize_node(state: PlacementState) -> dict:
    print(f"\n[synthesize_node] {len(state.get('research_data',[]))} snippets")
    if not state.get("research_data"):
        return {"synthesis": "No data."}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        block = "\n---\n".join(state["research_data"])
        resp  = model.generate_content(
            f"Summarize {state['company']} {state['role']} interview data "
            f"for {state.get('focus','DSA')} focus. 150 words max.\n\n{block[:3000]}"
        )
        s = resp.text.strip()
        print(f"  -> {len(s)} chars")
        return {"synthesis": s}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"synthesis": "failed", "errors": state.get("errors", []) + [str(e)]}


def question_node(state: PlacementState) -> dict:
    focus = state.get("focus", "DSA")
    print(f"\n[question_node] focus={focus}")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp  = model.generate_content(
            f"5 {focus} interview questions for {state['company']} {state['role']}. "
            f"Number Q1-Q5 with [Easy/Medium/Hard]. Context:\n{state.get('synthesis','')[:400]}"
        )
        parts = re.split(r"\n(?=Q\d+\.)", resp.text.strip())
        qs    = [p.strip() for p in parts if p.strip()] or [resp.text.strip()]
        print(f"  -> {len(qs)} questions")
        return {"questions": qs}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"questions": [], "errors": state.get("errors", []) + [str(e)]}


def error_node(state: PlacementState) -> dict:
    """Terminal node -- reached when retry limit exhausted."""
    msg = f"Stopped after {state.get('retry_count', 0)} retries with only {len(state.get('research_data',[]))} snippets."
    print(f"\n[error_node] {msg}")
    return {"errors": state.get("errors", []) + [msg], "synthesis": "FAILED"}


# ── Router ─────────────────────────────────────────────────────────────────────
# This is the NEW thing today. Takes state, returns a STRING.
# That string maps to a node name in add_conditional_edges().
def route_after_research(state: PlacementState) -> str:
    snippets = len(state.get("research_data", []))
    retries  = state.get("retry_count", 0)

    print(f"\n[router] snippets={snippets} (need>={MIN_SNIPPETS}) | retries={retries} (max={MAX_RETRIES})")

    if snippets >= MIN_SNIPPETS:
        print("  -> 'enough'")
        return "enough"
    if retries >= MAX_RETRIES:
        print("  -> 'error'  (retries exhausted)")
        return "error"
    print("  -> 'retry'  (looping back)")
    return "retry"


# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph():
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(PlacementState)

    builder.add_node("metadata_node",   metadata_node)
    builder.add_node("research_node",   research_node)
    builder.add_node("synthesize_node", synthesize_node)
    builder.add_node("question_node",   question_node)
    builder.add_node("error_node",      error_node)

    # Fixed edges (same as Day 23)
    builder.add_edge(START,              "metadata_node")
    builder.add_edge("metadata_node",    "research_node")
    builder.add_edge("synthesize_node",  "question_node")
    builder.add_edge("question_node",    END)
    builder.add_edge("error_node",       END)

    # NEW today: conditional edge replaces the fixed research->synthesize edge
    builder.add_conditional_edges(
        "research_node",         # source node
        route_after_research,    # router function
        {                        # branch name -> destination node
            "enough": "synthesize_node",
            "retry":  "research_node",   # points back to itself = retry loop
            "error":  "error_node",
        },
    )

    return builder.compile()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 24 -- Conditional Edges + Retry Loop")
    print("  NEW: add_conditional_edges() + router function + error_node")
    print("=" * 60)
    print(f"\n  Demo settings: MIN_SNIPPETS={MIN_SNIPPETS} | MAX_RETRIES={MAX_RETRIES}")
    print(f"  Attempt #1 fetches {DEMO_FIRST_CALL} result  -> triggers retry")
    print(f"  Attempt #2 fetches {NORMAL_CALL} results -> enough -> synthesize")

    graph = build_graph()

    state: PlacementState = {
        "company":       "Microsoft",
        "role":          "Software Engineer",
        "metadata":      {},
        "research_data": [],
        "retry_count":   0,
        "focus":         "System Design",
        "synthesis":     "",
        "questions":     [],
        "errors":        [],
    }

    print(f"\nTarget : {state['company']} -- {state['role']} | Focus: {state['focus']}")
    print("\n--- Running ---")

    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            print(f"\n  [{node_name}] wrote: {list(delta.keys())}")
            final.update(delta)

    print("\n" + "=" * 60)
    print("  RESULT")
    print("=" * 60)
    print(f"  Retries used : {final['retry_count']}")
    print(f"  Snippets     : {len(final['research_data'])}")
    print(f"  Questions    : {len(final['questions'])}")
    if final.get("synthesis") and final["synthesis"] not in ("FAILED", "No data."):
        print(f"\n  Synthesis (first 200 chars):\n  {final['synthesis'][:200]}")
    if final["errors"]:
        print(f"\n  Errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 24 done. Concept: add_conditional_edges(node, router_fn, {branch:node})")
    print("  Retry loop = conditional edge with 'retry' branch pointing back to source.")
    print("=" * 60)
