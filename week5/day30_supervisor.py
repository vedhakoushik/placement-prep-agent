"""
Day 30 -- Supervisor + Sub-Agents
===================================
ONE concept: a SupervisorAgent that reads a user message,
decides which specialist to call, and delegates.

What is NEW today:
  1. SupervisorAgent graph  -- route_node + conditional dispatch
  2. Three sub-agent graphs -- each is a compiled LangGraph
  3. Routing with Gemini    -- LLM reads message, returns JSON decision
  4. Agent-as-node pattern  -- each sub-agent is called inside a regular node

Sub-agents built today (simplified, real API calls):
  ResearchAgent  -- Tavily search + Gemini synthesis
  QuestionAgent  -- Gemini question generation
  FeedbackAgent  -- Gemini answer evaluation

No Pydantic yet (Day 31). No retries yet (Day 32). No tracing yet (Day 33).
Just the routing and delegation logic.
"""

import os, json, re
from typing import TypedDict, List
from dotenv import load_dotenv

load_dotenv()


# ═══════════════════════════════════════════════════════════════
#  SUPERVISOR STATE
# ═══════════════════════════════════════════════════════════════
class SupervisorState(TypedDict):
    user_message:   str
    agent_called:   str        # "research" | "question" | "feedback"
    routing_reason: str        # why the supervisor chose this agent
    company:        str        # extracted from message
    role:           str        # extracted from message
    focus:          str        # DSA | System Design | Behavioral
    question_text:  str        # for FeedbackAgent
    user_answer:    str        # for FeedbackAgent
    result:         dict       # whatever the sub-agent returned
    errors:         List[str]


# ═══════════════════════════════════════════════════════════════
#  RESEARCH AGENT (its own compiled LangGraph)
# ═══════════════════════════════════════════════════════════════
class ResearchState(TypedDict):
    company:       str
    role:          str
    research_data: List[str]
    synthesis:     str
    errors:        List[str]


def _research_search(state: ResearchState) -> dict:
    print(f"    [ResearchAgent/search] {state['company']}")
    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res = tavily.search(
            query=f"{state['company']} {state['role']} interview 2024 2025",
            max_results=4, search_depth="basic"
        )
        snippets = [r.get("content", "")[:400] for r in res.get("results", []) if r.get("content")]
        print(f"    -> {len(snippets)} snippets")
        return {"research_data": snippets}
    except Exception as e:
        print(f"    -> ERROR: {e}")
        return {"research_data": [], "errors": state.get("errors", []) + [str(e)]}


def _research_synthesize(state: ResearchState) -> dict:
    print(f"    [ResearchAgent/synthesize]", end="", flush=True)
    if not state.get("research_data"):
        return {"synthesis": "No data available."}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        block = "\n---\n".join(state["research_data"])
        resp  = model.generate_content(
            f"Summarize {state['company']} {state['role']} interview in 120 words. "
            f"Cover: top topics, round structure, difficulty.\n\n{block[:3000]}"
        )
        print(f" {len(resp.text)} chars")
        return {"synthesis": resp.text.strip()}
    except Exception as e:
        print(f" ERROR: {e}")
        return {"synthesis": "failed", "errors": state.get("errors", []) + [str(e)]}


def build_research_agent():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(ResearchState)
    b.add_node("search",     _research_search)
    b.add_node("synthesize", _research_synthesize)
    b.add_edge(START,      "search")
    b.add_edge("search",   "synthesize")
    b.add_edge("synthesize", END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  QUESTION AGENT (its own compiled LangGraph)
# ═══════════════════════════════════════════════════════════════
class QuestionState(TypedDict):
    company:   str
    role:      str
    focus:     str
    questions: List[str]
    errors:    List[str]


def _question_generate(state: QuestionState) -> dict:
    focus = state.get("focus", "DSA")
    print(f"    [QuestionAgent/generate] {state['company']} | {focus}", end="", flush=True)
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp  = model.generate_content(
            f"Generate 5 {focus} interview questions for {state['company']} {state['role']}. "
            f"Number Q1-Q5 with [Easy/Medium/Hard] tags."
        )
        parts = re.split(r"\n(?=Q\d+\.)", resp.text.strip())
        qs    = [p.strip() for p in parts if p.strip()] or [resp.text.strip()]
        print(f" {len(qs)} questions")
        return {"questions": qs}
    except Exception as e:
        print(f" ERROR: {e}")
        return {"questions": [], "errors": state.get("errors", []) + [str(e)]}


def build_question_agent():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(QuestionState)
    b.add_node("generate", _question_generate)
    b.add_edge(START, "generate")
    b.add_edge("generate", END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  FEEDBACK AGENT (its own compiled LangGraph)
# ═══════════════════════════════════════════════════════════════
class FeedbackState(TypedDict):
    question_text: str
    user_answer:   str
    score:         int
    strengths:     List[str]
    improvements:  List[str]
    errors:        List[str]


def _feedback_evaluate(state: FeedbackState) -> dict:
    print(f"    [FeedbackAgent/evaluate]", end="", flush=True)
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp  = model.generate_content(
            f"Evaluate this interview answer. Reply as JSON with keys: "
            f"score (0-10 int), strengths (list of str), improvements (list of str).\n\n"
            f"Question: {state['question_text']}\n"
            f"Answer: {state['user_answer']}"
        )
        text = resp.text.strip()
        # strip markdown code fences if present
        text = re.sub(r"```(?:json)?|```", "", text).strip()
        data = json.loads(text)
        print(f" score={data.get('score')}")
        return {
            "score":        int(data.get("score", 0)),
            "strengths":    data.get("strengths", []),
            "improvements": data.get("improvements", []),
        }
    except Exception as e:
        print(f" ERROR: {e}")
        return {"score": 0, "strengths": [], "improvements": [str(e)],
                "errors": state.get("errors", []) + [str(e)]}


def build_feedback_agent():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(FeedbackState)
    b.add_node("evaluate", _feedback_evaluate)
    b.add_edge(START, "evaluate")
    b.add_edge("evaluate", END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  SUPERVISOR NODES
# ═══════════════════════════════════════════════════════════════
def route_node(state: SupervisorState) -> dict:
    """
    Calls Gemini with the user message.
    Gemini returns JSON with: agent, company, role, focus, question_text, user_answer.
    """
    print(f"\n[supervisor/route] Reading: {state['user_message']!r}")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")

        resp = model.generate_content(
            "You are a routing agent. Classify this user message and extract fields.\n\n"
            "User message: " + repr(state["user_message"]) + "\n\n"
            "Reply as JSON with EXACTLY these keys:\n"
            '  "agent": "research" | "question" | "feedback"\n'
            '  "reason": one sentence why\n'
            '  "company": company name or ""\n'
            '  "role": job role or ""\n'
            '  "focus": "DSA" | "System Design" | "Behavioral" or "DSA"\n'
            '  "question_text": the interview question if feedback requested, else ""\n'
            '  "user_answer": the user answer if feedback requested, else ""\n\n'
            "Rules:\n"
            "  research  = user wants company/role information\n"
            "  question  = user wants interview questions generated\n"
            "  feedback  = user wants their answer evaluated\n\n"
            "Return only the JSON object, no markdown."
        )
        text = re.sub(r"```(?:json)?|```", "", resp.text.strip()).strip()
        data = json.loads(text)

        print(f"  -> agent={data.get('agent')!r} | reason={data.get('reason','')[:60]}")
        return {
            "agent_called":   data.get("agent", "research"),
            "routing_reason": data.get("reason", ""),
            "company":        data.get("company", ""),
            "role":           data.get("role", ""),
            "focus":          data.get("focus", "DSA"),
            "question_text":  data.get("question_text", ""),
            "user_answer":    data.get("user_answer", ""),
        }
    except Exception as e:
        print(f"  -> ERROR: {e} -- defaulting to research")
        return {
            "agent_called": "research", "routing_reason": f"error: {e}",
            "company": "", "role": "", "focus": "DSA",
            "question_text": "", "user_answer": "",
            "errors": state.get("errors", []) + [str(e)],
        }


def research_agent_node(state: SupervisorState) -> dict:
    """Invokes the ResearchAgent sub-graph."""
    print(f"\n[supervisor/research_agent_node] company={state['company']!r}")
    try:
        agent = build_research_agent()
        out   = agent.invoke({
            "company":       state.get("company", ""),
            "role":          state.get("role", ""),
            "research_data": [],
            "synthesis":     "",
            "errors":        [],
        })
        return {"result": {
            "type":      "research",
            "synthesis": out.get("synthesis"),
            "snippets":  len(out.get("research_data", [])),
        }}
    except Exception as e:
        print(f"  -> ERROR in ResearchAgent: {e}")
        return {
            "result": {"type": "research", "synthesis": f"Research failed: {e}", "snippets": 0},
            "errors": state.get("errors", []) + [f"research_agent_node: {e}"],
        }


def question_agent_node(state: SupervisorState) -> dict:
    """Invokes the QuestionAgent sub-graph."""
    print(f"\n[supervisor/question_agent_node] company={state['company']!r} focus={state['focus']!r}")
    try:
        agent = build_question_agent()
        out   = agent.invoke({
            "company":   state.get("company", ""),
            "role":      state.get("role", ""),
            "focus":     state.get("focus", "DSA"),
            "questions": [],
            "errors":    [],
        })
        return {"result": {"type": "question", "questions": out.get("questions", [])}}
    except Exception as e:
        print(f"  -> ERROR in QuestionAgent: {e}")
        return {
            "result": {"type": "question", "questions": []},
            "errors": state.get("errors", []) + [f"question_agent_node: {e}"],
        }


def feedback_agent_node(state: SupervisorState) -> dict:
    """Invokes the FeedbackAgent sub-graph."""
    print(f"\n[supervisor/feedback_agent_node]")
    try:
        agent = build_feedback_agent()
        out   = agent.invoke({
            "question_text": state.get("question_text", ""),
            "user_answer":   state.get("user_answer", ""),
            "score":         0,
            "strengths":     [],
            "improvements":  [],
            "errors":        [],
        })
        return {"result": {
            "type":         "feedback",
            "score":        out.get("score"),
            "strengths":    out.get("strengths"),
            "improvements": out.get("improvements"),
        }}
    except Exception as e:
        print(f"  -> ERROR in FeedbackAgent: {e}")
        return {
            "result": {"type": "feedback", "score": 0, "strengths": [], "improvements": [str(e)]},
            "errors": state.get("errors", []) + [f"feedback_agent_node: {e}"],
        }


# ═══════════════════════════════════════════════════════════════
#  SUPERVISOR ROUTER (reads agent_called from state)
# ═══════════════════════════════════════════════════════════════
def supervisor_router(state: SupervisorState) -> str:
    agent = state.get("agent_called", "research")
    print(f"\n[supervisor/router] -> {agent!r}")
    return agent   # "research" | "question" | "feedback"


# ═══════════════════════════════════════════════════════════════
#  BUILD SUPERVISOR GRAPH
# ═══════════════════════════════════════════════════════════════
def build_supervisor():
    from langgraph.graph import StateGraph, START, END

    b = StateGraph(SupervisorState)
    b.add_node("route_node",           route_node)
    b.add_node("research_agent_node",  research_agent_node)
    b.add_node("question_agent_node",  question_agent_node)
    b.add_node("feedback_agent_node",  feedback_agent_node)

    b.add_edge(START, "route_node")

    b.add_conditional_edges(
        "route_node",
        supervisor_router,
        {
            "research": "research_agent_node",
            "question": "question_agent_node",
            "feedback": "feedback_agent_node",
        },
    )

    b.add_edge("research_agent_node", END)
    b.add_edge("question_agent_node", END)
    b.add_edge("feedback_agent_node", END)

    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def run(message: str):
    """Run the supervisor with a user message and print results."""
    supervisor = build_supervisor()

    state: SupervisorState = {
        "user_message":   message,
        "agent_called":   "",
        "routing_reason": "",
        "company":        "",
        "role":           "",
        "focus":          "DSA",
        "question_text":  "",
        "user_answer":    "",
        "result":         {},
        "errors":         [],
    }

    final = dict(state)
    for event in supervisor.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            final.update(delta)

    return final


if __name__ == "__main__":
    print("=" * 60)
    print("  Day 30 -- Supervisor + Sub-Agents")
    print("  NEW: SupervisorAgent routes user messages to specialists")
    print("=" * 60)

    # Test all three routing paths
    test_messages = [
        "Research Razorpay SDE-2 interview process",
        "Give me 5 system design questions for Meesho Software Engineer",
        'I answered "Use a hashmap for O(1) lookup". How did I do? Question was: What is the best data structure for fast key-value access?',
    ]

    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"  USER: {msg[:70]}")
        print(f"{'='*60}")
        result = run(msg)
        print(f"\n  Agent called   : {result['agent_called']}")
        print(f"  Routing reason : {result['routing_reason']}")

        r = result.get("result", {})
        if r.get("type") == "research":
            print(f"  Synthesis      : {str(r.get('synthesis',''))[:200]}")
        elif r.get("type") == "question":
            print(f"  Questions ({len(r.get('questions',[]))}):")
            for q in r.get("questions", [])[:2]:
                print(f"    {q[:120]}")
        elif r.get("type") == "feedback":
            print(f"  Score      : {r.get('score')}/10")
            print(f"  Strengths  : {r.get('strengths')}")
            print(f"  Improve    : {r.get('improvements')}")

        if result.get("errors"):
            print(f"  Errors: {result['errors']}")

    print("\n" + "=" * 60)
    print("  Day 30 done.")
    print("  Concept: supervisor routes via Gemini JSON -> sub-agent LangGraph")
    print("  Each sub-agent is a compiled graph invoked as a regular node.")
    print("=" * 60)
