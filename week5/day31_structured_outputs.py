"""
Day 31 -- Structured Outputs Between Agents
=============================================
ONE concept: every agent returns a Pydantic model, not a plain string.

What is NEW today vs Day 30:
  1. Pydantic models  -- CompanyProfile, QuestionSet, FeedbackReport
  2. Gemini JSON mode -- response_mime_type="application/json"
  3. model.model_validate_json() -- parse + validate Gemini's output
  4. QuestionEvaluator -- a separate Gemini call that grades the QuestionSet

Why Pydantic?
  - Validated fields -- score is always an int, never a string
  - Composable       -- supervisor can inspect result.score directly
  - Self-documenting -- the model definition IS the contract between agents

Why JSON mode?
  Without it, Gemini might wrap the JSON in markdown ```json ... ```.
  With response_mime_type="application/json", you get raw JSON every time.

This day focuses on the output contracts, not the full pipeline.
Each agent is a single-node graph to keep it minimal.
"""

import os, json
from typing import TypedDict, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


# ═══════════════════════════════════════════════════════════════
#  PYDANTIC OUTPUT MODELS
#  These are the contracts between agents.
# ═══════════════════════════════════════════════════════════════

class CompanyProfile(BaseModel):
    company:          str
    role:             str
    founded:          str
    hq:               str
    type:             str              # product / service / MNC / startup
    difficulty:       str              # Easy / Medium / Hard
    key_topics:       List[str]        # e.g. ["arrays", "DP", "system design"]
    interview_rounds: List[str]        # e.g. ["OA", "Technical x2", "HR"]
    synthesis:        str              # 1-2 sentence summary


class Question(BaseModel):
    text:       str
    difficulty: str   # Easy | Medium | Hard
    topic:      str   # e.g. "Dynamic Programming"


class QuestionSet(BaseModel):
    company:                  str
    role:                     str
    focus:                    str
    questions:                List[Question]
    difficulty_distribution:  dict   # {"Easy": n, "Medium": n, "Hard": n}


class FeedbackReport(BaseModel):
    score:        int = Field(ge=0, le=10)
    strengths:    List[str]
    improvements: List[str]
    model_answer: str


class QuestionEvaluation(BaseModel):
    """Evaluator grades a QuestionSet for quality."""
    score:              int = Field(ge=0, le=10)
    relevance:          str   # are questions relevant to the company?
    difficulty_spread:  str   # is the mix of Easy/Medium/Hard good?
    topic_coverage:     str   # do questions cover the right topics?
    verdict:            str   # one-sentence overall assessment


# ═══════════════════════════════════════════════════════════════
#  GEMINI JSON HELPER
# ═══════════════════════════════════════════════════════════════
def gemini_json(prompt: str) -> str:
    """
    Calls Gemini with JSON mode enabled.
    Returns raw JSON string -- no markdown fences.
    """
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    resp = model.generate_content(prompt)
    return resp.text.strip()


# ═══════════════════════════════════════════════════════════════
#  AGENT NODES (one per agent, each returns its Pydantic model)
# ═══════════════════════════════════════════════════════════════

# ── State ──────────────────────────────────────────────────────
class AgentState(TypedDict):
    company:        str
    role:           str
    focus:          str
    question_text:  str
    user_answer:    str
    profile:        dict    # CompanyProfile serialized
    question_set:   dict    # QuestionSet serialized
    feedback:       dict    # FeedbackReport serialized
    evaluation:     dict    # QuestionEvaluation serialized
    errors:         List[str]


def research_node(state: AgentState) -> dict:
    """Returns a CompanyProfile (validated Pydantic)."""
    company = state["company"]
    role    = state["role"]
    print(f"\n[research_node] {company} | {role}", end="", flush=True)
    try:
        # Search first
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        res    = tavily.search(
            query=f"{company} {role} interview process topics rounds",
            max_results=3, search_depth="basic"
        )
        context = "\n---\n".join(r.get("content", "")[:400] for r in res.get("results", []))

        raw = gemini_json(
            f"Return a JSON CompanyProfile for {company} (role: {role}).\n\n"
            f"Context:\n{context[:2000]}\n\n"
            f"Required JSON fields:\n"
            f'  "company": str,\n'
            f'  "role": str,\n'
            f'  "founded": str,\n'
            f'  "hq": str,\n'
            f'  "type": str,\n'
            f'  "difficulty": "Easy" | "Medium" | "Hard",\n'
            f'  "key_topics": list of 3-5 strings,\n'
            f'  "interview_rounds": list of strings,\n'
            f'  "synthesis": one concise sentence\n'
        )
        profile = CompanyProfile.model_validate_json(raw)
        print(f" -> CompanyProfile valid (topics={profile.key_topics[:2]})")
        return {"profile": profile.model_dump()}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"errors": state.get("errors", []) + [f"research_node: {e}"]}


def question_node(state: AgentState) -> dict:
    """Returns a QuestionSet (validated Pydantic)."""
    company = state["company"]
    role    = state["role"]
    focus   = state.get("focus", "DSA")
    print(f"\n[question_node] {company} | {focus}", end="", flush=True)
    try:
        raw = gemini_json(
            f"Generate 5 {focus} interview questions for {company} {role}.\n\n"
            f"Return JSON with EXACTLY this structure:\n"
            f'{{"company": "{company}", "role": "{role}", "focus": "{focus}",\n'
            f' "questions": [\n'
            f'   {{"text": "...", "difficulty": "Easy|Medium|Hard", "topic": "..."}},\n'
            f'   ...\n'
            f' ],\n'
            f' "difficulty_distribution": {{"Easy": n, "Medium": n, "Hard": n}}\n'
            f'}}'
        )
        qset = QuestionSet.model_validate_json(raw)
        print(f" -> QuestionSet valid ({len(qset.questions)} questions)")
        return {"question_set": qset.model_dump()}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"errors": state.get("errors", []) + [f"question_node: {e}"]}


def feedback_node(state: AgentState) -> dict:
    """Returns a FeedbackReport (validated Pydantic)."""
    print(f"\n[feedback_node]", end="", flush=True)
    try:
        raw = gemini_json(
            f"Evaluate this interview answer. Return JSON FeedbackReport.\n\n"
            f"Question: {state['question_text']}\n"
            f"Answer:   {state['user_answer']}\n\n"
            f"Required JSON:\n"
            f'{{"score": int 0-10, "strengths": [str,...], '
            f'"improvements": [str,...], "model_answer": "str"}}'
        )
        report = FeedbackReport.model_validate_json(raw)
        print(f" -> FeedbackReport valid (score={report.score})")
        return {"feedback": report.model_dump()}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"errors": state.get("errors", []) + [f"feedback_node: {e}"]}


def evaluator_node(state: AgentState) -> dict:
    """
    NEW today: after QuestionAgent runs, a separate call grades the QuestionSet.
    This is the 'evaluator' concept -- an LLM reviewing another LLM's output.
    """
    print(f"\n[evaluator_node]", end="", flush=True)
    qset = state.get("question_set")
    if not qset:
        print(" -> no question_set to evaluate")
        return {}
    try:
        questions_text = "\n".join(
            f"  {i+1}. [{q['difficulty']}] {q['text']}"
            for i, q in enumerate(qset.get("questions", []))
        )
        raw = gemini_json(
            f"Grade this set of interview questions for {qset.get('company')} "
            f"{qset.get('role')} ({qset.get('focus')} focus).\n\n"
            f"Questions:\n{questions_text}\n\n"
            f"Return JSON QuestionEvaluation:\n"
            f'{{"score": int 0-10, "relevance": "str", '
            f'"difficulty_spread": "str", "topic_coverage": "str", "verdict": "str"}}'
        )
        ev = QuestionEvaluation.model_validate_json(raw)
        print(f" -> QuestionEvaluation valid (score={ev.score})")
        return {"evaluation": ev.model_dump()}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {"errors": state.get("errors", []) + [f"evaluator_node: {e}"]}


# ═══════════════════════════════════════════════════════════════
#  GRAPH: research -> question -> evaluator -> feedback (for demo)
# ═══════════════════════════════════════════════════════════════
def build_graph():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(AgentState)
    b.add_node("research",  research_node)
    b.add_node("question",  question_node)
    b.add_node("evaluator", evaluator_node)
    b.add_node("feedback",  feedback_node)

    b.add_edge(START,      "research")
    b.add_edge("research", "question")
    b.add_edge("question", "evaluator")
    b.add_edge("evaluator","feedback")
    b.add_edge("feedback", END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 31 -- Structured Outputs (Pydantic + JSON mode)")
    print("  NEW: Pydantic models, gemini JSON mode, evaluator node")
    print("=" * 60)

    graph = build_graph()

    state: AgentState = {
        "company":       "Flipkart",
        "role":          "Software Engineer",
        "focus":         "DSA",
        "question_text": "What data structure would you use for implementing an LRU cache?",
        "user_answer":   "I would use a combination of a HashMap and a Doubly Linked List. The HashMap gives O(1) access and the DLL gives O(1) insertion/deletion.",
        "profile":       {},
        "question_set":  {},
        "feedback":      {},
        "evaluation":    {},
        "errors":        [],
    }

    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            print(f"\n  [{node_name}] wrote: {list(delta.keys())}")
            final.update(delta)

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    if final.get("profile"):
        p = CompanyProfile(**final["profile"])
        print(f"\n  CompanyProfile:")
        print(f"    founded : {p.founded}")
        print(f"    hq      : {p.hq}")
        print(f"    topics  : {p.key_topics}")
        print(f"    rounds  : {p.interview_rounds}")

    if final.get("question_set"):
        qs = QuestionSet(**final["question_set"])
        print(f"\n  QuestionSet:")
        print(f"    distribution: {qs.difficulty_distribution}")
        for q in qs.questions[:2]:
            print(f"    [{q.difficulty}] {q.text[:100]}")

    if final.get("evaluation"):
        ev = QuestionEvaluation(**final["evaluation"])
        print(f"\n  QuestionEvaluation (evaluator grades the questions):")
        print(f"    score   : {ev.score}/10")
        print(f"    verdict : {ev.verdict}")

    if final.get("feedback"):
        fb = FeedbackReport(**final["feedback"])
        print(f"\n  FeedbackReport:")
        print(f"    score        : {fb.score}/10")
        print(f"    strengths    : {fb.strengths}")
        print(f"    improvements : {fb.improvements}")

    if final.get("errors"):
        print(f"\n  Errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 31 done.")
    print("  Every node returns a Pydantic model -- validated, typed, composable.")
    print("  JSON mode = no markdown fences. model_validate_json = one-line parse.")
    print("=" * 60)
