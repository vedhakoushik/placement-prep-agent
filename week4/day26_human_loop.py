"""
Day 26 -- Human-in-the-Loop
=============================
ONE concept: pause the graph mid-execution, wait for human input, resume.

What is NEW today vs Day 24:
  1. MemorySaver   -- a checkpointer that saves graph state between calls
  2. thread_id     -- identifies which conversation the checkpoint belongs to
  3. interrupt()   -- called inside a node to PAUSE and yield a value to the caller
  4. Command(resume=value) -- resumes the paused graph with the human's input

Nothing else changes. The nodes are the same Day 24 pipeline.
The graph structure is the same. The ONLY new thing is the pause/resume mechanism.

How interrupt() works step by step:
  1. Node calls:  value = interrupt({"ask": "Choose focus", "options": [...]})
  2. LangGraph:   saves full graph state to MemorySaver
  3. LangGraph:   raises GraphInterrupt -- graph STOPS, returns to caller
  4. Caller:      catches the interrupt, shows options to human, gets input
  5. Caller:      calls graph.stream(Command(resume=human_input), config=SAME_CONFIG)
  6. interrupt(): returns human_input -- node continues from that exact line

The SAME thread_id in config is what links call #1 (before interrupt)
and call #2 (after interrupt). Without it, there is no continuity.
"""

import os, re
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()

MIN_SNIPPETS = 3
MAX_RETRIES  = 3


# ── State (same as Day 24) ────────────────────────────────────────────────────
class PlacementState(TypedDict):
    company:       str
    role:          str
    metadata:      dict
    research_data: List[str]
    retry_count:   int
    focus:         str        # the human sets this during the interrupt
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
        print(f"  -> HQ={meta['hq']}")
        return {"metadata": meta}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"metadata": {}, "errors": state.get("errors", []) + [str(e)]}


def research_node(state: PlacementState) -> dict:
    count = state.get("retry_count", 0)
    print(f"\n[research_node] attempt #{count + 1}")
    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res    = tavily.search(
            query=f"{state['company']} {state['role']} interview experience 2024 2025",
            max_results=5, search_depth="basic"
        )
        snippets = [
            r.get("content", "")[:500]
            for r in res.get("results", [])
            if r.get("content", "").strip()
        ]
        print(f"  -> {len(snippets)} snippets")
        return {"research_data": snippets, "retry_count": count + 1}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"research_data": [], "retry_count": count + 1,
                "errors": state.get("errors", []) + [str(e)]}


def route_after_research(state: PlacementState) -> str:
    snippets = len(state.get("research_data", []))
    retries  = state.get("retry_count", 0)
    print(f"\n[router] snippets={snippets} | retries={retries}")
    if snippets >= MIN_SNIPPETS:
        return "enough"
    if retries >= MAX_RETRIES:
        return "error"
    return "retry"


# ── NEW today: synthesize_node calls interrupt() ──────────────────────────────
def synthesize_node(state: PlacementState) -> dict:
    """
    Research is done. But we don't know what focus the student wants yet.
    Pause here, show the human what we found, ask them to choose.
    """
    from langgraph.types import interrupt  # the new thing today

    print(f"\n[synthesize_node] research done ({len(state.get('research_data',[]))} snippets)")
    print("  Calling interrupt() -- graph will pause here.")

    # interrupt() pauses the graph and sends this payload to the caller.
    # When resumed, it returns whatever the caller passed to Command(resume=...).
    focus = interrupt({
        "message": "Research complete. What should I focus on?",
        "options": ["DSA", "System Design", "Behavioral"],
        "company": state["company"],
        "role":    state["role"],
    })

    # ← execution resumes here after Command(resume=focus) is called
    print(f"\n[synthesize_node] resumed. Human chose: {focus!r}")

    if not state.get("research_data"):
        return {"synthesis": "No data.", "focus": focus}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model  = genai.GenerativeModel("gemini-2.5-flash")
        block  = "\n---\n".join(state["research_data"])
        resp   = model.generate_content(
            f"Summarize {state['company']} {state['role']} interview for {focus} focus. "
            f"150 words max.\n\n{block[:3000]}"
        )
        s = resp.text.strip()
        print(f"  -> synthesis {len(s)} chars")
        return {"synthesis": s, "focus": focus}
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {"synthesis": "failed", "focus": focus,
                "errors": state.get("errors", []) + [str(e)]}


def question_node(state: PlacementState) -> dict:
    focus = state.get("focus", "DSA")
    print(f"\n[question_node] focus={focus}")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp  = model.generate_content(
            f"5 {focus} questions for {state['company']} {state['role']}. "
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
    msg = f"Max retries ({state.get('retry_count',0)}) reached."
    print(f"\n[error_node] {msg}")
    return {"errors": state.get("errors", []) + [msg]}


# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph(checkpointer):
    """checkpointer is REQUIRED for interrupt() to work."""
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(PlacementState)
    builder.add_node("metadata_node",   metadata_node)
    builder.add_node("research_node",   research_node)
    builder.add_node("synthesize_node", synthesize_node)
    builder.add_node("question_node",   question_node)
    builder.add_node("error_node",      error_node)

    builder.add_edge(START,              "metadata_node")
    builder.add_edge("metadata_node",    "research_node")
    builder.add_edge("synthesize_node",  "question_node")
    builder.add_edge("question_node",    END)
    builder.add_edge("error_node",       END)

    builder.add_conditional_edges(
        "research_node", route_after_research,
        {"enough": "synthesize_node", "retry": "research_node", "error": "error_node"},
    )

    return builder.compile(checkpointer=checkpointer)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    print("=" * 60)
    print("  Day 26 -- Human-in-the-Loop")
    print("  NEW: MemorySaver + interrupt() + Command(resume=)")
    print("=" * 60)

    checkpointer = MemorySaver()
    graph        = build_graph(checkpointer)

    # thread_id = identifier for this conversation's checkpoint
    config = {"configurable": {"thread_id": "day26-flipkart"}}

    state: PlacementState = {
        "company":       "Flipkart",
        "role":          "Software Engineer",
        "metadata":      {},
        "research_data": [],
        "retry_count":   0,
        "focus":         "",       # will be set by the human
        "synthesis":     "",
        "questions":     [],
        "errors":        [],
    }

    print(f"\nTarget : {state['company']} -- {state['role']}")

    # ── PHASE 1: run until interrupt ──────────────────────────────────────────
    print("\n--- Phase 1: running until interrupt ---")

    interrupt_value = None
    try:
        for event in graph.stream(state, config=config, stream_mode="updates"):
            for node_name, delta in event.items():
                print(f"  [{node_name}] wrote: {list(delta.keys())}")
    except Exception as exc:
        # LangGraph raises when interrupt() is hit
        print(f"\n  Graph paused ({type(exc).__name__})")
        # The interrupt value is inside the exception
        if exc.args:
            raw = exc.args[0]
            interrupt_value = raw[0].value if hasattr(raw, '__iter__') and hasattr(raw[0], 'value') else raw

    # Show what the interrupt sent us
    print("\n" + "=" * 60)
    print("  INTERRUPT RECEIVED -- HUMAN DECISION POINT")
    print("=" * 60)
    if isinstance(interrupt_value, dict):
        print(f"\n  {interrupt_value.get('message','Choose focus:')}")
        print(f"  Company : {interrupt_value.get('company')}")
        print(f"  Options : {interrupt_value.get('options')}")
    else:
        print(f"\n  Graph paused at synthesize_node. Choose a focus area.")

    # Simulate human choosing (in a real app this would be a UI input)
    human_choice = "DSA"
    print(f"\n  Human selects: {human_choice!r}")

    # ── PHASE 2: resume with human's choice ──────────────────────────────────
    print("\n--- Phase 2: resuming with Command(resume=) ---")

    final = {}
    try:
        for event in graph.stream(
            Command(resume=human_choice),
            config=config,             # SAME thread_id -- same checkpoint
            stream_mode="updates",
        ):
            for node_name, delta in event.items():
                print(f"  [{node_name}] wrote: {list(delta.keys())}")
                final.update(delta)
    except Exception as e:
        print(f"  Error during resume: {e}")

    # Output
    print("\n" + "=" * 60)
    print("  RESULT")
    print("=" * 60)
    print(f"\n  Focus chosen : {human_choice}")
    print(f"  Questions    : {len(final.get('questions', []))}")
    if final.get("synthesis"):
        print(f"\n  Synthesis (first 200 chars):\n  {final['synthesis'][:200]}")
    if final.get("questions"):
        print(f"\n  First question:\n  {final['questions'][0][:200]}")
    if final.get("errors"):
        print(f"\n  Errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 26 done.")
    print("  interrupt() = pause + checkpoint. Command(resume=) = play.")
    print("  Same thread_id links the two stream() calls.")
    print("=" * 60)
