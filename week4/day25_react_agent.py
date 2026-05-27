"""
Day 25 -- ReAct Agent
======================
ONE concept: LLM in a loop deciding which tool to call next.

ReAct = Reason + Act (paper: Yao et al. 2022)
  - The LLM reasons about what it needs to know
  - Then ACTS by calling a tool
  - Reads the result, reasons again, acts again
  - Stops when it has enough information to answer

What is NEW today vs Day 24:
  1. State has `messages` list (conversation history)
  2. `llm_node`  -- calls Gemini, reads last messages, decides next action
  3. `tool_node` -- executes whichever tool the LLM chose
  4. Graph has a LOOP: llm -> router -> tool -> llm -> router -> ...
  5. Router reads LLM output text to pick "tool" or "end"

Tools available to the LLM:
  SEARCH: <query>    -- Tavily web search
  ANSWER: <text>     -- done, this is the final answer

The LLM outputs one of these prefixes. The router reads it and routes.
No function-calling API needed -- pure text parsing, exactly like the original paper.

This day does NOT build on the placement prep pipeline from Day 23/24.
It is a standalone ReAct demo for any research question.
"""

import os
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()

MAX_LOOPS = 5  # safety: stop even if LLM keeps calling tools


# ── State ──────────────────────────────────────────────────────────────────────
# Simpler than Day 23/24 -- this day is about the loop, not the pipeline.
class ReactState(TypedDict):
    question:   str           # the research task given to the agent
    messages:   List[dict]    # [{role: user|model|tool, content: str}]
    loop_count: int           # how many llm->tool cycles have run
    answer:     str           # set when LLM outputs ANSWER:
    tools_used: List[str]     # log of every tool call (for inspection)
    errors:     List[str]


# ── Tool ──────────────────────────────────────────────────────────────────────
def run_search(query: str) -> str:
    """Tavily web search. Returns concatenated snippets."""
    try:
        from tavily import TavilyClient
        tavily  = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = tavily.search(query=query, max_results=3, search_depth="basic")
        snippets = [
            r.get("content", "")[:400]
            for r in results.get("results", [])
            if r.get("content", "").strip()
        ]
        return "\n---\n".join(snippets) if snippets else "No results."
    except Exception as e:
        return f"Search error: {e}"


# ── Prompt template ───────────────────────────────────────────────────────────
SYSTEM = """You are a research agent. You research topics by calling a web search tool.

To search the web, output EXACTLY:
  SEARCH: <your search query>

When you have enough information to answer the original question, output EXACTLY:
  ANSWER: <your complete answer>

Rules:
- Make at most 3 SEARCH calls
- Each SEARCH query must be different from previous ones
- After each search result, decide: do I know enough? If yes -> ANSWER, if no -> SEARCH
- Output ONLY one line starting with SEARCH: or ANSWER:"""


# ── Nodes ─────────────────────────────────────────────────────────────────────
def llm_node(state: ReactState) -> dict:
    """
    Sends the full conversation to Gemini.
    Parses its response for SEARCH: or ANSWER:.
    Appends the response to messages.
    """
    print(f"\n[llm_node] loop #{state.get('loop_count', 0) + 1}")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Build conversation string from message history
        lines = [SYSTEM, ""]
        for msg in state.get("messages", []):
            if msg["role"] == "user":
                lines.append(f"Question: {msg['content']}")
            elif msg["role"] == "model":
                lines.append(f"Agent: {msg['content']}")
            elif msg["role"] == "tool":
                lines.append(f"Search result:\n{msg['content']}")
        lines.append("Agent:")

        resp = model.generate_content("\n".join(lines))
        text = resp.text.strip()
        print(f"  LLM output: {text[:100]}")

        return {
            "messages":   state.get("messages", []) + [{"role": "model", "content": text}],
            "loop_count": state.get("loop_count", 0) + 1,
        }
    except Exception as e:
        print(f"  -> ERROR: {e}")
        err_text = f"ANSWER: Could not complete research due to error: {e}"
        return {
            "messages":   state.get("messages", []) + [{"role": "model", "content": err_text}],
            "loop_count": state.get("loop_count", 0) + 1,
            "errors":     state.get("errors", []) + [str(e)],
        }


def tool_node(state: ReactState) -> dict:
    """
    Reads the last model message, extracts SEARCH: query, runs it.
    Appends the result to messages.
    """
    last = state["messages"][-1]["content"].strip()

    if not last.startswith("SEARCH:"):
        return {}  # nothing to do

    query = last[len("SEARCH:"):].strip()
    print(f"\n[tool_node] SEARCH: {query!r}")

    result = run_search(query)
    print(f"  -> {len(result)} chars returned")

    return {
        "messages":   state["messages"] + [{"role": "tool", "content": result}],
        "tools_used": state.get("tools_used", []) + [f"SEARCH({query})"],
    }


# ── Router ────────────────────────────────────────────────────────────────────
# NEW today: the router reads the LLM's TEXT OUTPUT to decide the branch.
# In Day 23/24 the router read numerical state values (snippet count, retry count).
# Here it reads semantic content.
def should_continue(state: ReactState) -> str:
    last   = state["messages"][-1]["content"].strip()
    loops  = state.get("loop_count", 0)

    if loops >= MAX_LOOPS:
        print(f"\n[router] safety limit ({MAX_LOOPS}) reached -> 'end'")
        return "end"

    if last.startswith("SEARCH:"):
        print(f"\n[router] LLM wants to search -> 'tool'")
        return "tool"

    # ANSWER: or anything else -> done
    print(f"\n[router] LLM gave answer -> 'end'")
    return "end"


# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph():
    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(ReactState)
    builder.add_node("llm",  llm_node)
    builder.add_node("tool", tool_node)

    builder.add_edge(START, "llm")

    builder.add_conditional_edges(
        "llm",
        should_continue,
        {"tool": "tool", "end": END},
    )

    # After tool: ALWAYS back to llm (unconditional)
    builder.add_edge("tool", "llm")

    return builder.compile()


# ── Extract final answer ──────────────────────────────────────────────────────
def get_answer(messages: list) -> str:
    for msg in reversed(messages):
        if msg["role"] == "model" and msg["content"].startswith("ANSWER:"):
            return msg["content"][len("ANSWER:"):].strip()
    for msg in reversed(messages):
        if msg["role"] == "model":
            return msg["content"]
    return "No answer."


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 25 -- ReAct Agent")
    print("  NEW: messages state + llm_node + tool_node + loop")
    print("  LLM decides: SEARCH again OR give ANSWER")
    print("=" * 60)

    graph = build_graph()

    question = "What are the top DSA topics and interview rounds at Amazon SDE?"

    state: ReactState = {
        "question":   question,
        "messages":   [{"role": "user", "content": question}],
        "loop_count": 0,
        "answer":     "",
        "tools_used": [],
        "errors":     [],
    }

    print(f"\nQuestion: {question}")
    print("\n--- Running ReAct loop ---")

    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            if "messages" in delta:
                count = len(delta["messages"])
                print(f"  [{node_name}] +{count} message(s)")
            elif delta:
                print(f"  [{node_name}] wrote: {list(delta.keys())}")
            final.update(delta)

    answer = get_answer(final.get("messages", []))

    print("\n" + "=" * 60)
    print("  RESULT")
    print("=" * 60)
    print(f"\n  Loops     : {final['loop_count']}")
    print(f"  Tools used: {final['tools_used']}")
    print(f"\n  Answer:\n  {answer}")
    if final["errors"]:
        print(f"\n  Errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 25 done. Concept: messages list + llm->tool loop.")
    print("  Router reads LLM text (not state numbers) to decide branch.")
    print("=" * 60)
