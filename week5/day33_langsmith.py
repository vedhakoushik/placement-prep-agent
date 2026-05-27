"""
Day 33 -- Observability with LangSmith
=========================================
ONE concept: every node and every LLM call appears as a named span in LangSmith.

What is NEW today:
  1. LANGCHAIN_TRACING_V2 env var  -- turns on automatic LangGraph tracing
  2. @traceable decorator          -- wraps raw Gemini calls as named spans
  3. langchain-google-genai        -- LangChain-native Gemini (auto-traced)
  4. Slowest-node analysis         -- reads run metadata to find the bottleneck

How tracing works:
  LangGraph uses langchain-core internally.
  When LANGCHAIN_TRACING_V2=true, every graph.stream() call creates a trace.
  Each node is a span. You can see: input, output, latency, token count.

  For raw google.generativeai calls, you must add @traceable manually
  because they bypass the LangChain callback system.

Setup (one-time):
  1. Go to https://smith.langchain.com and sign up (free)
  2. Create a project named "placement-prep-agent"
  3. Copy your API key
  4. Add to .env:
       LANGSMITH_API_KEY=ls__...
       LANGCHAIN_PROJECT=placement-prep-agent

Install: pip install langsmith langchain-google-genai
"""

import os, time
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()


# ═══════════════════════════════════════════════════════════════
#  LANGSMITH SETUP
#  These env vars are read by langchain-core automatically.
#  Set them BEFORE importing any langchain/langgraph modules.
# ═══════════════════════════════════════════════════════════════
def setup_tracing():
    key = os.getenv("LANGSMITH_API_KEY", "")
    if not key:
        print("  WARNING: LANGSMITH_API_KEY not set in .env")
        print("  Traces will NOT be sent to LangSmith.")
        print("  Add LANGSMITH_API_KEY=ls__... to your .env file.")
        print("  Get one free at: https://smith.langchain.com\n")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]     = key
    os.environ["LANGCHAIN_PROJECT"]     = os.getenv("LANGCHAIN_PROJECT", "placement-prep-agent")
    print(f"  LangSmith tracing ON -> project: {os.environ['LANGCHAIN_PROJECT']}")
    return True


# ═══════════════════════════════════════════════════════════════
#  @traceable -- wraps raw Gemini calls as LangSmith spans
# ═══════════════════════════════════════════════════════════════
try:
    from langsmith import traceable
except ImportError:
    # Fallback: no-op decorator if langsmith not installed
    def traceable(name=None, **kwargs):
        def decorator(fn): return fn
        return decorator


@traceable(name="tavily-search", run_type="tool")
def traced_search(query: str) -> List[str]:
    """Tavily search -- appears as a 'tool' span in LangSmith."""
    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res = tavily.search(query=query, max_results=3, search_depth="basic")
        return [r.get("content", "")[:400] for r in res.get("results", []) if r.get("content")]
    except Exception as e:
        return [f"search error: {e}"]


@traceable(name="gemini-synthesis", run_type="llm")
def traced_gemini(prompt: str) -> str:
    """Raw Gemini call -- @traceable makes it a named span in LangSmith."""
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp  = model.generate_content(prompt)
    return resp.text.strip()


# ═══════════════════════════════════════════════════════════════
#  STATE + NODES
# ═══════════════════════════════════════════════════════════════
class ResearchState(TypedDict):
    company:       str
    role:          str
    focus:         str
    research_data: List[str]
    synthesis:     str
    questions:     List[str]
    timings:       dict       # node_name -> elapsed_seconds
    errors:        List[str]


def metadata_node(state: ResearchState) -> dict:
    t0 = time.time()
    print(f"\n[metadata_node] {state['company']}")
    # Using traceable Gemini call
    try:
        snippets = traced_search(f"{state['company']} company founded headquarters size")
        content  = " ".join(snippets)
        result   = traced_gemini(
            f"From this text, reply: Founded: <year> | HQ: <city> | Type: <type>\n\n{content[:1500]}"
        )
        print(f"  -> {result[:80]}")
    except Exception as e:
        print(f"  -> ERROR: {e}")
    elapsed = round(time.time() - t0, 2)
    t = dict(state.get("timings", {}))
    t["metadata_node"] = elapsed
    print(f"  -> elapsed: {elapsed}s")
    return {"timings": t}


def research_node(state: ResearchState) -> dict:
    t0 = time.time()
    print(f"\n[research_node] {state['company']}")
    try:
        snippets = traced_search(
            f"{state['company']} {state['role']} interview questions experience 2024"
        )
        print(f"  -> {len(snippets)} snippets")
    except Exception as e:
        snippets = []
        print(f"  -> ERROR: {e}")
    elapsed = round(time.time() - t0, 2)
    t = dict(state.get("timings", {}))
    t["research_node"] = elapsed
    print(f"  -> elapsed: {elapsed}s")
    return {"research_data": snippets, "timings": t}


def synthesize_node(state: ResearchState) -> dict:
    t0 = time.time()
    print(f"\n[synthesize_node]", end="", flush=True)
    snippets = state.get("research_data", [])
    if not snippets:
        return {"synthesis": "No data."}
    try:
        block     = "\n---\n".join(snippets)
        synthesis = traced_gemini(
            f"Summarize {state['company']} {state['role']} interview in 100 words. "
            f"Focus: {state.get('focus','DSA')}.\n\n{block[:3000]}"
        )
        print(f" {len(synthesis)} chars")
    except Exception as e:
        synthesis = "failed"
        print(f" ERROR: {e}")
    elapsed = round(time.time() - t0, 2)
    t = dict(state.get("timings", {}))
    t["synthesize_node"] = elapsed
    print(f"  -> elapsed: {elapsed}s")
    return {"synthesis": synthesis, "timings": t}


def question_node(state: ResearchState) -> dict:
    t0 = time.time()
    import re
    focus = state.get("focus", "DSA")
    print(f"\n[question_node] focus={focus}", end="", flush=True)
    try:
        result = traced_gemini(
            f"5 {focus} questions for {state['company']} {state['role']}. "
            f"Q1-Q5 with [Easy/Medium/Hard]."
        )
        parts = re.split(r"\n(?=Q\d+\.)", result.strip())
        qs    = [p.strip() for p in parts if p.strip()] or [result]
        print(f" {len(qs)} questions")
    except Exception as e:
        qs = []
        print(f" ERROR: {e}")
    elapsed = round(time.time() - t0, 2)
    t = dict(state.get("timings", {}))
    t["question_node"] = elapsed
    print(f"  -> elapsed: {elapsed}s")
    return {"questions": qs, "timings": t}


# ═══════════════════════════════════════════════════════════════
#  GRAPH
# ═══════════════════════════════════════════════════════════════
def build_graph():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(ResearchState)
    b.add_node("metadata_node",  metadata_node)
    b.add_node("research_node",  research_node)
    b.add_node("synthesize_node", synthesize_node)
    b.add_node("question_node",  question_node)
    b.add_edge(START,             "metadata_node")
    b.add_edge("metadata_node",   "research_node")
    b.add_edge("research_node",   "synthesize_node")
    b.add_edge("synthesize_node", "question_node")
    b.add_edge("question_node",   END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import subprocess, sys
    for pkg in ["langsmith", "langchain-google-genai"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

    print("=" * 60)
    print("  Day 33 -- LangSmith Observability")
    print("  NEW: LANGCHAIN_TRACING_V2 + @traceable + timing per node")
    print("=" * 60)

    tracing_on = setup_tracing()

    graph = build_graph()

    state: ResearchState = {
        "company":       "Zomato",
        "role":          "Software Engineer",
        "focus":         "DSA",
        "research_data": [],
        "synthesis":     "",
        "questions":     [],
        "timings":       {},
        "errors":        [],
    }

    print(f"\nTarget: {state['company']} -- {state['role']}\n")

    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            final.update(delta)

    # ── Slowest-node analysis ─────────────────────────────────
    print("\n" + "=" * 60)
    print("  NODE TIMING ANALYSIS")
    print("=" * 60)
    timings = final.get("timings", {})
    if timings:
        sorted_nodes = sorted(timings.items(), key=lambda x: x[1], reverse=True)
        total = sum(timings.values())
        print(f"\n  {'Node':<22} {'Time':>8}  {'% of total':>12}")
        print(f"  {'-'*22} {'-'*8}  {'-'*12}")
        for node, t in sorted_nodes:
            pct = f"{100*t/total:.0f}%"
            flag = " <-- SLOWEST" if node == sorted_nodes[0][0] else ""
            print(f"  {node:<22} {t:>7.2f}s  {pct:>12}{flag}")
        print(f"\n  Total: {total:.2f}s")
        slowest = sorted_nodes[0][0]
        print(f"\n  Optimization tip for {slowest}:")
        if "synthesize" in slowest or "question" in slowest:
            print("    -> This is an LLM call. Swap gemini-2.5-flash to gemini-1.5-flash")
            print("       for 2x faster generation at slightly lower quality.")
        elif "research" in slowest or "metadata" in slowest:
            print("    -> This is a Tavily call. Use search_depth='basic' (already set).")
            print("       Or cache results: skip re-fetching if company was researched today.")

    if tracing_on:
        project = os.environ.get("LANGCHAIN_PROJECT", "placement-prep-agent")
        print(f"\n  Traces sent to LangSmith!")
        print(f"  View at: https://smith.langchain.com -> project '{project}'")
        print(f"  You'll see: each node as a span, token counts, exact prompts.")
    else:
        print(f"\n  Add LANGSMITH_API_KEY to .env to enable cloud traces.")
        print(f"  Get one free at: https://smith.langchain.com")

    print("\n" + "=" * 60)
    print("  Day 33 done.")
    print("  LANGCHAIN_TRACING_V2=true -> auto-traces all LangGraph runs.")
    print("  @traceable -> manually traces raw Gemini calls.")
    print("  timings dict -> local perf analysis without LangSmith.")
    print("=" * 60)
