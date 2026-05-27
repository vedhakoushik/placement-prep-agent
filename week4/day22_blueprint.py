"""
Day 22 — Why LangGraph Exists
==============================================
A chain is a straight line. An agent needs:
  - LOOPS   → search → not enough → search again
  - BRANCHES → DSA path vs system design path
  - PAUSES  → wait for human input, then resume

LangGraph models your agent as a STATE MACHINE:
  - Nodes  = functions that do work (search, synthesize, generate)
  - Edges  = connections between nodes (always go to X)
  - Conditional edges = router functions (go to X or Y based on state)
  - State  = a dict that every node reads from and writes to

MENTAL MODEL
─────────────────────────────────────────────────────────────────
  LangChain chain:     A → B → C → D        (no way back)
  LangGraph:           A → B → C → D        (can loop)
                             ↑___↓ (if condition)

FULL PLACEMENT PREP AGENT — GRAPH BLUEPRINT
==============================================

  Drawn on paper first, then coded Day 23 onwards.

  ┌──────────────────────────────────────────────────────────┐
  │                                                          │
  │   START                                                  │
  │     │                                                    │
  │     ▼                                                    │
  │  [metadata_node]                                         │
  │   fetch company basics: founded, HQ, size, type          │
  │     │                                                    │
  │     ▼                                                    │
  │  [research_node] ◄──────────────────────────┐            │
  │   Tavily search for interview data           │            │
  │     │                                       │            │
  │     ▼                                       │            │
  │  [router: enough_data?]                     │            │
  │     │                                       │            │
  │  enough ──────────────────────────────────► │ (loop)     │
  │     │                    not enough ────────┘            │
  │     ▼  (retry > 3 → error node)                          │
  │                                                          │
  │  [synthesize_node]  ◄── HUMAN PAUSE (Day 26)             │
  │   distill raw research → key facts                       │
  │   ask: "Focus DSA / System Design / Behavioral?"         │
  │     │                                                    │
  │     ▼                                                    │
  │  [question_node]                                         │
  │   generate interview questions based on                  │
  │   synthesized data + user's chosen focus                 │
  │     │                                                    │
  │     ▼                                                    │
  │  [store_node]                                            │
  │   upsert results into ChromaDB qa_store                  │
  │     │                                                    │
  │     ▼                                                    │
  │   END                                                    │
  └──────────────────────────────────────────────────────────┘

NODES DEFINED:
  metadata_node  → input: company, role
                   output: state.metadata (founded, HQ, size)

  research_node  → input: company, role, metadata, retry_count
                   output: state.research_data (list of strings)
                   uses: Tavily search

  router         → input: research_data, retry_count
                   returns: "synthesize" | "research" | "error"
                   condition: len < 3 AND retry < 3 → loop
                              retry >= 3 → error
                              else → synthesize

  synthesize_node → input: research_data, focus (from human)
                    output: state.synthesis (condensed facts)
                    uses: Gemini LLM

  question_node  → input: synthesis, focus, company, role
                   output: state.questions (list)
                   uses: Gemini LLM
                   PAUSES here for human input (Day 26)

  store_node     → input: company, questions, synthesis
                   output: state.stored = True
                   uses: ChromaDB

STATE SCHEMA (Day 23):
  {
    "company":        str,
    "role":           str,
    "metadata":       dict,
    "research_data":  list[str],
    "retry_count":    int,
    "focus":          str,        # DSA / System Design / Behavioral
    "synthesis":      str,
    "questions":      list[str],
    "errors":         list[str],
    "stored":         bool,
  }

TODAY'S TASK: Blueprint understood. Ready to code Day 23.
"""

# Run this file to print the blueprint summary.
if __name__ == "__main__":
    blueprint = """
╔══════════════════════════════════════════════════════════════╗
║       PLACEMENT PREP AGENT — LANGGRAPH BLUEPRINT             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  START → metadata → research ←──────(retry loop)            ║
║                         │                                    ║
║                      [router]                                ║
║                    /    |    \\                               ║
║               loop   error  synthesize ← [HUMAN PAUSE]       ║
║                                │                             ║
║                           question_node                       ║
║                                │                             ║
║                           store_node                         ║
║                                │                             ║
║                              END                             ║
╠══════════════════════════════════════════════════════════════╣
║  Why not a chain?                                            ║
║  - Research might fail → need to retry (LOOP)                ║
║  - User picks focus → DSA vs SysDesign (BRANCH)             ║
║  - Human confirms focus → pause & resume (PAUSE)             ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(blueprint)

    print("State schema:")
    state_schema = {
        "company":       "str  — target company name",
        "role":          "str  — e.g. SDE, Data Analyst",
        "metadata":      "dict — founded, HQ, size",
        "research_data": "list — raw Tavily search results",
        "retry_count":   "int  — how many search retries so far",
        "focus":         "str  — DSA | System Design | Behavioral",
        "synthesis":     "str  — LLM-condensed research summary",
        "questions":     "list — generated interview questions",
        "errors":        "list — any errors encountered",
        "stored":        "bool — whether results saved to ChromaDB",
    }
    for k, v in state_schema.items():
        print(f"  {k:16s}: {v}")

    print("\nWeek 4 roadmap:")
    days = [
        ("Day 22", "Blueprint (today) — understand the graph before coding"),
        ("Day 23", "StateGraph — linear START→research→synthesize→question→END"),
        ("Day 24", "Conditional edges + retry loop"),
        ("Day 25", "ReAct Agent — llm_node + tool_node + router loop"),
        ("Day 26", "Human-in-the-Loop — interrupt_before + Command(resume=)"),
        ("Day 27-28", "SqliteSaver persistence + compare_companies()"),
    ]
    for day, desc in days:
        print(f"  {day}: {desc}")
