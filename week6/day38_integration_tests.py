"""
Day 38 -- Integration Tests
============================
ONE concept: test a REAL LangGraph run end-to-end — graph builds, nodes
execute, state flows correctly — without calling real APIs.

What is NEW vs Day 37 (unit tests):
  Day 37 → unittest.mock.patch on individual functions   (unit)
  Day 38 → build the whole graph, run graph.stream()     (integration)

New topics today:
  1. SqliteSaver      -- real on-disk checkpoint in a temp directory
  2. Thread IDs       -- {"configurable": {"thread_id": "..."}}
  3. Interrupt/resume -- interrupt_before=["approve_node"], then resume
  4. State snapshots  -- graph.get_state(config)
  5. Cross-run persistence -- state survives between .stream() calls

Why integration tests matter:
  - Unit tests catch bugs in one function.
  - Integration tests catch bugs in how nodes connect:
      wrong key names in state, missing edges, reducer conflicts.
  - The SqliteSaver test proves checkpointing actually works —
    if the agent crashes mid-run, it can pick up where it left off.

Run:
  pip install pytest langgraph
  python -m pytest week6/day38_integration_tests.py -v

All tests use mocked Tavily + Gemini — no API keys needed.
"""

import os
import sys
import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from typing   import TypedDict, List, Annotated
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from langgraph.graph           import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver


# ═══════════════════════════════════════════════════════════════
#  SHARED STATE
# ═══════════════════════════════════════════════════════════════
class ResearchState(TypedDict):
    company:       str
    role:          str
    focus:         str
    research_data: List[str]
    synthesis:     str
    questions:     List[str]
    approved:      bool          # set during interrupt/resume
    errors:        List[str]


# ═══════════════════════════════════════════════════════════════
#  INLINE NODES  (same logic as week 5, but importable without .env)
# ═══════════════════════════════════════════════════════════════
def _gemini(prompt: str) -> str:
    """Thin wrapper — real code lives in day34_35_app.py."""
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    return genai.GenerativeModel("gemini-2.5-flash").generate_content(prompt).text.strip()


def _search(query: str) -> List[str]:
    """Thin wrapper — real code lives in day34_35_app.py."""
    from tavily import TavilyClient
    res = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", "")).search(
        query=query, max_results=3, search_depth="basic"
    )
    return [r.get("content", "")[:400] for r in res.get("results", [])]


def research_node(state: ResearchState) -> dict:
    try:
        data = _search(f"{state['company']} {state['role']} interview {state['focus']}")
    except Exception as e:
        data = []
        return {"research_data": data, "errors": [str(e)]}
    return {"research_data": data}


def synthesize_node(state: ResearchState) -> dict:
    if not state.get("research_data"):
        return {"synthesis": "No data available."}
    try:
        block = "\n".join(state["research_data"][:3])
        text  = _gemini(f"Summarise {state['company']} interview in 60 words.\n{block[:1500]}")
    except Exception as e:
        text = f"Error: {e}"
    return {"synthesis": text}


def question_node(state: ResearchState) -> dict:
    try:
        text = _gemini(
            f"3 {state['focus']} questions for {state['company']} {state['role']}."
        )
        qs = [l.strip() for l in text.split("\n") if l.strip()][:3]
    except Exception as e:
        qs = [f"Error: {e}"]
    return {"questions": qs}


def approve_node(state: ResearchState) -> dict:
    """Human-in-the-loop node — the graph pauses HERE in interrupt tests."""
    return {"approved": True}


# ═══════════════════════════════════════════════════════════════
#  GRAPH FACTORY
# ═══════════════════════════════════════════════════════════════
def build_graph(checkpointer=None, interrupt_before=None):
    """
    Build the research graph.
    Pass checkpointer=SqliteSaver(...) for persistence tests.
    Pass interrupt_before=["approve_node"] for HITL tests.
    """
    b = StateGraph(ResearchState)
    b.add_node("research_node",   research_node)
    b.add_node("synthesize_node", synthesize_node)
    b.add_node("approve_node",    approve_node)
    b.add_node("question_node",   question_node)

    b.add_edge(START,            "research_node")
    b.add_edge("research_node",  "synthesize_node")
    b.add_edge("synthesize_node","approve_node")
    b.add_edge("approve_node",   "question_node")
    b.add_edge("question_node",  END)

    kwargs = {}
    if checkpointer:
        kwargs["checkpointer"] = checkpointer
    if interrupt_before:
        kwargs["interrupt_before"] = interrupt_before

    return b.compile(**kwargs)


# ═══════════════════════════════════════════════════════════════
#  MOCK HELPERS
# ═══════════════════════════════════════════════════════════════
# Resolved at import time — whatever path pytest used to load this module.
_MOD = __name__

FAKE_SNIPPETS = [
    "Google interviews heavily test DSA. Expect 2 DSA rounds and 1 system design.",
    "LeetCode medium/hard problems are common at Google SDE-2 level.",
    "Google values clear problem decomposition and time complexity analysis.",
]

FAKE_SYNTHESIS = "Google SDE-2 interviews focus on DSA and system design. Prepare LeetCode mediums."

FAKE_QUESTIONS = [
    "Q1. Two Sum variant — find pairs with target sum. [Easy]",
    "Q2. Design a URL shortener. [Medium]",
    "Q3. Serialize and deserialize a binary tree. [Hard]",
]


def mock_search():
    """
    Patches _search() in this module directly — no Tavily import needed.
    This is the correct integration-test pattern: patch at the call site,
    not deep inside the library.
    """
    return patch(f"{_MOD}._search", return_value=FAKE_SNIPPETS)


def mock_gemini(answers: list):
    """
    Patches _gemini() in this module to return answers[0], answers[1], …
    Each call advances the index; last answer repeats if calls exceed list.
    """
    call_count = {"n": 0}

    def fake(prompt: str) -> str:
        idx = min(call_count["n"], len(answers) - 1)
        call_count["n"] += 1
        return answers[idx]

    return patch(f"{_MOD}._gemini", side_effect=fake)


INIT_STATE: ResearchState = {
    "company":       "Google",
    "role":          "SDE-2",
    "focus":         "DSA",
    "research_data": [],
    "synthesis":     "",
    "questions":     [],
    "approved":      False,
    "errors":        [],
}


# ═══════════════════════════════════════════════════════════════
#  TESTS
# ═══════════════════════════════════════════════════════════════

class TestGraphStructure:
    """Does the graph build without errors and have the right nodes?"""

    def test_graph_builds(self):
        g = build_graph()
        assert g is not None

    def test_graph_has_all_nodes(self):
        g = build_graph()
        # get_graph() returns the underlying Graph with .nodes dict
        # LangGraph adds virtual __start__ and __end__ nodes automatically
        nodes = set(g.get_graph().nodes.keys())
        assert "research_node"   in nodes
        assert "synthesize_node" in nodes
        assert "approve_node"    in nodes
        assert "question_node"   in nodes

    def test_graph_edge_count(self):
        g = build_graph()
        # START→research, research→synthesize, synthesize→approve,
        # approve→question, question→END  = 5 edges
        edges = list(g.get_graph().edges)
        assert len(edges) == 5


class TestFullRun:
    """Run the complete graph end-to-end with mocked APIs."""

    def test_research_data_populated(self):
        """research_node should fill research_data from Tavily."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
            assert len(final.get("research_data", [])) == 3

    def test_synthesis_written(self):
        """synthesize_node should produce a non-empty synthesis string."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
            assert final.get("synthesis", "") != ""
            assert "Google" in final["synthesis"] or len(final["synthesis"]) > 10

    def test_questions_generated(self):
        """question_node should return at least 1 question."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
            assert len(final.get("questions", [])) >= 1

    def test_approved_flag_set(self):
        """approve_node should set approved=True."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
            assert final.get("approved") is True

    def test_errors_empty_on_success(self):
        """No errors should be present on a clean run."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
            assert final.get("errors", []) == []

    def test_node_event_order(self):
        """Nodes must fire in the correct sequence."""
        with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
            g     = build_graph()
            order = []
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                order.extend(ev.keys())

            expected = ["research_node", "synthesize_node", "approve_node", "question_node"]
            assert order == expected


class TestSqliteCheckpointer:
    """
    SqliteSaver saves state to disk after every node.
    Tests prove that checkpointing actually persists data
    and that a second run on the same thread_id sees prior state.
    """

    def test_checkpoint_file_created(self, tmp_path):
        """A .db file must appear on disk after running the graph."""
        db_path = str(tmp_path / "cp.db")
        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp)
            cfg = {"configurable": {"thread_id": "t1"}}
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg, stream_mode="updates"):
                    pass
        assert Path(db_path).exists()

    def test_state_persists_across_runs(self, tmp_path):
        """
        Run the graph once. Then create a NEW graph object on the same DB
        and call get_state() — it must return the saved synthesis.
        """
        db_path = str(tmp_path / "cp.db")
        cfg     = {"configurable": {"thread_id": "t2"}}

        # First run
        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp)
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg, stream_mode="updates"):
                    pass

        # Second access — fresh graph object, same DB
        with SqliteSaver.from_conn_string(db_path) as cp2:
            g2 = build_graph(checkpointer=cp2)
            snap = g2.get_state(cfg)
            assert snap.values.get("synthesis", "") != ""

    def test_different_threads_are_isolated(self, tmp_path):
        """
        Thread A researches Google; Thread B researches Flipkart.
        They share one DB file but must never mix state.
        """
        db_path  = str(tmp_path / "cp.db")
        cfg_a    = {"configurable": {"thread_id": "google_run"}}
        cfg_b    = {"configurable": {"thread_id": "flipkart_run"}}
        state_b  = {**INIT_STATE, "company": "Flipkart", "role": "PM",
                    "focus": "Behavioral"}

        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp)
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg_a, stream_mode="updates"):
                    pass
            with mock_search(), mock_gemini(["Flipkart focuses on PM skills.", "Q1. Walk me through a product."]):
                for _ in g.stream(state_b, cfg_b, stream_mode="updates"):
                    pass

            snap_a = g.get_state(cfg_a)
            snap_b = g.get_state(cfg_b)

        assert snap_a.values["company"] == "Google"
        assert snap_b.values["company"] == "Flipkart"


class TestInterruptResume:
    """
    Human-in-the-loop: graph pauses before approve_node.
    The human (or test) inspects state, optionally modifies it,
    then resumes by calling stream(None, config).
    """

    def test_graph_pauses_at_interrupt(self, tmp_path):
        """
        After research + synthesis, the graph should STOP
        before approve_node and NOT have set approved=True yet.
        """
        db_path = str(tmp_path / "cp.db")
        cfg     = {"configurable": {"thread_id": "hitl_1"}}

        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp, interrupt_before=["approve_node"])
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg, stream_mode="updates"):
                    pass

            snap = g.get_state(cfg)
            # Graph paused — approved should still be False
            assert snap.values.get("approved") is False
            # Next node to run should be approve_node
            assert snap.next == ("approve_node",)

    def test_resume_completes_graph(self, tmp_path):
        """
        After pausing, call stream(None, config) to resume.
        The graph finishes and questions are generated.
        """
        db_path = str(tmp_path / "cp.db")
        cfg     = {"configurable": {"thread_id": "hitl_2"}}

        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp, interrupt_before=["approve_node"])

            # Run until interrupt
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg, stream_mode="updates"):
                    pass

            # Resume — pass None as input (continue from checkpoint)
            with mock_gemini(["\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(None, cfg, stream_mode="updates"):
                    pass

            snap = g.get_state(cfg)
            assert snap.values.get("approved") is True
            assert len(snap.values.get("questions", [])) >= 1

    def test_state_update_before_resume(self, tmp_path):
        """
        Simulate the human MODIFYING state before resuming
        (e.g. injecting extra research_data).
        The modified value must be visible in the final snapshot.
        """
        db_path  = str(tmp_path / "cp.db")
        cfg      = {"configurable": {"thread_id": "hitl_3"}}
        extra    = "Extra context added by human reviewer."

        with SqliteSaver.from_conn_string(db_path) as cp:
            g = build_graph(checkpointer=cp, interrupt_before=["approve_node"])

            # Run until interrupt
            with mock_search(), mock_gemini([FAKE_SYNTHESIS, "\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(dict(INIT_STATE), cfg, stream_mode="updates"):
                    pass

            # Human injects extra data before resuming
            current = g.get_state(cfg)
            new_data = list(current.values.get("research_data", [])) + [extra]
            g.update_state(cfg, {"research_data": new_data})

            # Resume
            with mock_gemini(["\n".join(FAKE_QUESTIONS)]):
                for _ in g.stream(None, cfg, stream_mode="updates"):
                    pass

            snap = g.get_state(cfg)
            assert extra in snap.values.get("research_data", [])


class TestErrorRecovery:
    """Nodes should degrade gracefully — errors stored in state, not raised."""

    def test_search_failure_fills_errors(self):
        """When _search raises, errors list should be non-empty."""
        def broken_search(query):
            raise RuntimeError("network down")

        with patch(f"{_MOD}._search", side_effect=broken_search):
            g = build_graph()
            final = {}
            for ev in g.stream(dict(INIT_STATE), stream_mode="updates"):
                for _, delta in ev.items():
                    final.update(delta)
        assert len(final.get("errors", [])) > 0

    def test_empty_research_gives_fallback_synthesis(self):
        """synthesize_node with empty research_data returns a fallback string."""
        empty_state = {**INIT_STATE, "research_data": []}
        result = synthesize_node(empty_state)
        assert "No data" in result["synthesis"]

    def test_graph_still_completes_after_search_failure(self):
        """
        Even when research_node produces no data, the rest of the graph
        should still run (synthesize returns fallback, questions fire).
        """
        def broken_search(query):
            raise RuntimeError("timeout")

        with patch(f"{_MOD}._search", side_effect=broken_search), \
             mock_gemini(["No data available.", "\n".join(FAKE_QUESTIONS)]):
            g = build_graph()
            events = list(g.stream(dict(INIT_STATE), stream_mode="updates"))

        node_names = [k for ev in events for k in ev.keys()]
        assert "question_node" in node_names   # graph ran to END


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import subprocess, sys as _sys
    print("=" * 60)
    print("  Day 38 -- Integration Tests")
    print("  NEW: SqliteSaver · interrupt_before · update_state")
    print("=" * 60)
    subprocess.run(
        [_sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=ROOT,
    )
