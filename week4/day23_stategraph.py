"""
Day 23 -- First StateGraph
===========================
ONE concept: TypedDict state + linear node pipeline.

Graph:
  START -> metadata_node -> research_node -> synthesize_node -> question_node -> END

What this day covers:
  - Defining a TypedDict as the state schema
  - Writing node functions (take full state, return partial dict)
  - Registering nodes with add_node()
  - Connecting them with add_edge() (fixed, straight line -- no branching)
  - compile() + stream() to run and observe

Nothing else. No retry logic. No router. No human pause. No persistence.
"""

import os, re
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()


# ── State ──────────────────────────────────────────────────────────────────────
# This is the single dict that flows through every node.
# Each node reads whatever it needs and writes back only the keys it changed.
class PlacementState(TypedDict):
    company:       str          # input
    role:          str          # input
    metadata:      dict         # filled by metadata_node
    research_data: List[str]    # filled by research_node
    focus:         str          # input (DSA / System Design / Behavioral)
    synthesis:     str          # filled by synthesize_node
    questions:     List[str]    # filled by question_node
    errors:        List[str]    # any node can append errors here


# ── Nodes ─────────────────────────────────────────────────────────────────────
# Rule: every node receives the FULL state dict.
#       every node returns a PARTIAL dict (only the keys it changed).
#       LangGraph merges the partial dict into state before calling the next node.

def metadata_node(state: PlacementState) -> dict:
    """Fetch company basics: founded, HQ, size, type."""
    print(f"\n[metadata_node] company={state['company']!r}")
    try:
        from tavily import TavilyClient
        import google.generativeai as genai

        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model  = genai.GenerativeModel("gemini-2.5-flash")

        res     = tavily.search(
            query=f"{state['company']} company founded headquarters size employees",
            max_results=3, search_depth="basic"
        )
        content = " ".join(r.get("content", "") for r in res.get("results", []))

        resp = model.generate_content(
            f"From this text about {state['company']}, reply EXACTLY in this format:\n"
            "Founded: <year or Unknown>\n"
            "HQ: <city, country or Unknown>\n"
            "Size: <employee count or Unknown>\n"
            "Type: <product/service/startup/MNC>\n\n"
            f"Text: {content[:2000]}"
        )
        meta = {"founded": "Unknown", "hq": "Unknown", "size": "Unknown", "type": "Unknown"}
        for line in resp.text.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                if k in meta:
                    meta[k] = v.strip()

        print(f"  -> Founded={meta['founded']} | HQ={meta['hq']} | Type={meta['type']}")
        return {"metadata": meta}

    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "metadata": {"founded": "?", "hq": "?", "size": "?", "type": "?"},
            "errors": state.get("errors", []) + [f"metadata_node: {e}"],
        }


def research_node(state: PlacementState) -> dict:
    """Search Tavily for interview experience data."""
    print(f"\n[research_node] company={state['company']!r} role={state['role']!r}")
    try:
        from tavily import TavilyClient

        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res    = tavily.search(
            query=f"{state['company']} {state['role']} interview questions experience 2024 2025",
            max_results=5, search_depth="basic"
        )
        snippets = [
            r.get("content", "")[:500]
            for r in res.get("results", [])
            if r.get("content", "").strip()
        ]
        print(f"  -> {len(snippets)} snippets fetched")
        return {"research_data": snippets}

    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "research_data": [],
            "errors": state.get("errors", []) + [f"research_node: {e}"],
        }


def synthesize_node(state: PlacementState) -> dict:
    """Condense raw research into a focused summary using Gemini."""
    snippets = state.get("research_data", [])
    print(f"\n[synthesize_node] {len(snippets)} snippets | focus={state.get('focus','DSA')!r}")

    if not snippets:
        return {"synthesis": "No research data available."}

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")

        meta  = state.get("metadata", {})
        block = "\n---\n".join(snippets)

        resp = model.generate_content(
            f"Summarize {state['company']} {state['role']} interview info for someone "
            f"focusing on {state.get('focus','DSA')}. Max 150 words.\n"
            f"Company: Founded {meta.get('founded','?')}, HQ {meta.get('hq','?')}, "
            f"Type {meta.get('type','?')}.\n\n"
            f"Research:\n{block[:3000]}"
        )
        synthesis = resp.text.strip()
        print(f"  -> {len(synthesis)} chars")
        return {"synthesis": synthesis}

    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "synthesis": "Synthesis failed.",
            "errors": state.get("errors", []) + [f"synthesize_node: {e}"],
        }


def question_node(state: PlacementState) -> dict:
    """Generate 5 interview questions based on synthesis and focus."""
    focus = state.get("focus", "DSA")
    print(f"\n[question_node] focus={focus!r}")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")

        resp = model.generate_content(
            f"Generate exactly 5 {focus} interview questions for "
            f"{state['company']} {state['role']}.\n"
            f"Number them Q1-Q5. Add [Easy/Medium/Hard] tag after each number.\n"
            f"Context:\n{state.get('synthesis', '')[:500]}"
        )
        parts = re.split(r"\n(?=Q\d+\.)", resp.text.strip())
        questions = [p.strip() for p in parts if p.strip()] or [resp.text.strip()]
        print(f"  -> {len(questions)} questions generated")
        return {"questions": questions}

    except Exception as e:
        print(f"  -> ERROR: {e}")
        return {
            "questions": [],
            "errors": state.get("errors", []) + [f"question_node: {e}"],
        }


# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph():
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(PlacementState)

    # Register nodes
    builder.add_node("metadata_node",   metadata_node)
    builder.add_node("research_node",   research_node)
    builder.add_node("synthesize_node", synthesize_node)
    builder.add_node("question_node",   question_node)

    # Connect in a straight line -- add_edge = always go to next
    builder.add_edge(START,              "metadata_node")
    builder.add_edge("metadata_node",    "research_node")
    builder.add_edge("research_node",    "synthesize_node")
    builder.add_edge("synthesize_node",  "question_node")
    builder.add_edge("question_node",    END)

    return builder.compile()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 23 -- First StateGraph")
    print("  Graph: START -> metadata -> research -> synthesize -> question -> END")
    print("=" * 60)

    graph = build_graph()
    print(f"\nNodes: {[n for n in graph.nodes if not n.startswith('__')]}")

    # Seed state -- only the inputs. Nodes fill the rest.
    state: PlacementState = {
        "company":       "Google",
        "role":          "Software Engineer",
        "metadata":      {},
        "research_data": [],
        "focus":         "DSA",
        "synthesis":     "",
        "questions":     [],
        "errors":        [],
    }

    print(f"\nTarget : {state['company']} -- {state['role']}")
    print(f"Focus  : {state['focus']}")
    print("\n--- Running (stream_mode='updates' shows each node's return value) ---")

    # stream_mode="updates" yields {node_name: {keys_this_node_returned}}
    # This makes it clear EXACTLY what each node contributed.
    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            keys = list(delta.keys())
            print(f"\n  [{node_name}] wrote keys: {keys}")
            final.update(delta)

    # Final output
    print("\n" + "=" * 60)
    print("  FINAL STATE")
    print("=" * 60)
    print(f"\n  company  : {final['company']}")
    print(f"  metadata : {final['metadata']}")
    print(f"  snippets : {len(final['research_data'])}")
    print(f"  synthesis: {final['synthesis'][:200]}")
    print(f"\n  Questions ({len(final['questions'])}):")
    for q in final["questions"][:3]:
        print(f"    {q[:150]}")
    if final["errors"]:
        print(f"\n  Errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 23 done. Concept: TypedDict state + linear add_edge pipeline.")
    print("=" * 60)
