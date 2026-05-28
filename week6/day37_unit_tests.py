"""
Day 37 -- pytest Unit Tests
============================
ONE concept: unittest.mock.patch -- replace real API calls with controlled fakes.

What this day does:
  1. Mocks TavilyClient so tests run without hitting the real search API
  2. Mocks google.generativeai so Gemini never fires (no quota burned)
  3. Tests routing logic (pure Python -- no mocking needed at all)
  4. Tests Pydantic model validation (pure Python)
  5. Tests a full research pipeline with both APIs mocked end-to-end

Why mocking matters:
  - Tests run in <1 second total instead of 5-10s per API call
  - Tests run free -- zero API quota consumed
  - Tests work fully offline and in CI/CD pipelines
  - A failure means YOUR logic is wrong, not a rate limit or network blip

How patch() works:
  with patch("module.ClassName") as MockClass:
      MockClass.return_value.method.return_value = your_fake_data
      # Inside this block, ClassName() returns MockClass.return_value
      # -- the real API is never called

Run:
  pip install pytest
  python -m pytest week6/day37_unit_tests.py -v

All 21 tests pass with zero real API calls.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ================================================================
#  MINIMAL INLINE FUNCTIONS
#  Self-contained copies of the key logic from weeks 4-5.
#  Day 40 will pull these into src/utils.py -- for now they live
#  here so Day 37 is fully isolated and readable on its own.
# ================================================================

def route_after_research(state: dict) -> str:
    """
    Pure routing logic from day24_conditional_edges.py.
    Returns 'enough' / 'retry' / 'error' -- no API calls, no imports.
    """
    data    = state.get("research_data", [])
    retries = state.get("retry_count", 0)

    if len(data) == 0 and retries >= 2:
        return "error"
    if len(data) < 3:
        return "retry"
    return "enough"


def research_node(state: dict) -> dict:
    """
    Calls TavilyClient to fetch interview snippets.
    Patched in tests so no real HTTP request fires.
    """
    from tavily import TavilyClient
    tavily  = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
    results = tavily.search(
        query=f"{state['company']} {state['role']} interview",
        max_results=5,
        search_depth="basic",
    )
    snippets = [
        r.get("content", "")[:300]
        for r in results.get("results", [])
        if r.get("content")
    ]
    return {
        "research_data": snippets,
        "retry_count":   state.get("retry_count", 0) + 1,
    }


def synthesize_node(state: dict) -> dict:
    """
    Calls Gemini to synthesize a summary.
    Patched in tests so no real LLM call fires.
    """
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.5-flash")
    block = "\n".join(state.get("research_data", [])[:2])
    resp  = model.generate_content(
        f"Summarize {state['company']} interview in 80 words.\n\n{block[:2000]}"
    )
    return {"synthesis": resp.text.strip()}


# Pydantic models (from day31_structured_outputs.py)
from pydantic import BaseModel, Field

class CompanyProfile(BaseModel):
    name:    str
    founded: str
    hq:      str
    focus:   str

class Question(BaseModel):
    text:       str
    difficulty: str   # Easy / Medium / Hard

class FeedbackReport(BaseModel):
    score:        int = Field(ge=0, le=10)
    strengths:    List[str]
    improvements: List[str]


# ================================================================
#  GROUP 1 -- Routing logic (pure Python, no mocking needed)
# ================================================================

class TestRouting:
    """
    route_after_research() only reads a dict -- no imports, no API.
    These tests run instantly and never need a mock.
    """

    def test_enough_when_3_snippets(self):
        state = {"research_data": ["a", "b", "c"], "retry_count": 0}
        assert route_after_research(state) == "enough"

    def test_enough_with_many_snippets(self):
        state = {"research_data": ["x"] * 10, "retry_count": 0}
        assert route_after_research(state) == "enough"

    def test_retry_when_fewer_than_3_snippets(self):
        state = {"research_data": ["only one"], "retry_count": 0}
        assert route_after_research(state) == "retry"

    def test_retry_when_zero_snippets_but_retries_below_limit(self):
        state = {"research_data": [], "retry_count": 1}
        assert route_after_research(state) == "retry"

    def test_error_when_empty_and_retries_exhausted(self):
        state = {"research_data": [], "retry_count": 2}
        assert route_after_research(state) == "error"

    def test_exactly_3_snippets_is_enough_not_retry(self):
        state = {"research_data": ["a", "b", "c"], "retry_count": 5}
        assert route_after_research(state) == "enough"

    def test_2_snippets_is_retry_not_enough(self):
        state = {"research_data": ["a", "b"], "retry_count": 0}
        assert route_after_research(state) == "retry"


# ================================================================
#  GROUP 2 -- research_node (Tavily mocked)
# ================================================================

class TestResearchNode:
    """
    patch('tavily.TavilyClient') intercepts the constructor.
    MockClient.return_value is the fake instance returned by TavilyClient().
    MockClient.return_value.search.return_value is what .search() returns.
    """

    def test_returns_correct_snippet_count(self):
        fake = {"results": [
            {"content": "Google interviews focus on DSA."},
            {"content": "Expect LeetCode medium problems."},
            {"content": "System design for senior roles."},
        ]}
        with patch("tavily.TavilyClient") as MockClient:
            MockClient.return_value.search.return_value = fake
            state  = {"company": "Google", "role": "SDE",
                      "research_data": [], "retry_count": 0}
            result = research_node(state)

        assert len(result["research_data"]) == 3

    def test_snippet_content_preserved(self):
        fake = {"results": [{"content": "Atlassian values collaboration."}]}
        with patch("tavily.TavilyClient") as MockClient:
            MockClient.return_value.search.return_value = fake
            state  = {"company": "Atlassian", "role": "SDE",
                      "research_data": [], "retry_count": 0}
            result = research_node(state)

        assert "Atlassian" in result["research_data"][0]

    def test_empty_results_returns_empty_list(self):
        with patch("tavily.TavilyClient") as MockClient:
            MockClient.return_value.search.return_value = {"results": []}
            state  = {"company": "X", "role": "Y",
                      "research_data": [], "retry_count": 0}
            result = research_node(state)

        assert result["research_data"] == []

    def test_retry_count_increments_by_1(self):
        with patch("tavily.TavilyClient") as MockClient:
            MockClient.return_value.search.return_value = {"results": [{"content": "x"}]}
            state  = {"company": "X", "role": "Y",
                      "research_data": [], "retry_count": 3}
            result = research_node(state)

        assert result["retry_count"] == 4

    def test_snippet_length_capped_at_300_chars(self):
        long_content = "Z" * 500
        fake = {"results": [{"content": long_content}]}
        with patch("tavily.TavilyClient") as MockClient:
            MockClient.return_value.search.return_value = fake
            state  = {"company": "X", "role": "Y",
                      "research_data": [], "retry_count": 0}
            result = research_node(state)

        assert len(result["research_data"][0]) == 300


# ================================================================
#  GROUP 3 -- synthesize_node (Gemini mocked)
# ================================================================

class TestSynthesizeNode:
    """
    Two patches needed:
      patch("google.generativeai.GenerativeModel") -- the model class
      patch("google.generativeai.configure")       -- the configure() call

    MagicMock() auto-creates any attribute or method you access on it.
    We only set .text on the response object since that's all the node reads.
    """

    def _fake_model(self, text: str):
        """Helper: build a mock model whose generate_content() returns text."""
        mock_resp  = MagicMock()
        mock_resp.text = text
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_resp
        return mock_model

    def test_synthesis_text_returned(self):
        expected = "Google focuses on data structures and system design."
        with patch("google.generativeai.GenerativeModel") as MockModel, \
             patch("google.generativeai.configure"):
            MockModel.return_value = self._fake_model(expected)
            state  = {"company": "Google", "role": "SDE",
                      "research_data": ["snippet 1", "snippet 2"]}
            result = synthesize_node(state)

        assert result["synthesis"] == expected

    def test_synthesis_stripped_of_whitespace(self):
        with patch("google.generativeai.GenerativeModel") as MockModel, \
             patch("google.generativeai.configure"):
            MockModel.return_value = self._fake_model("  Leading and trailing.  ")
            state  = {"company": "X", "role": "Y", "research_data": ["a"]}
            result = synthesize_node(state)

        assert result["synthesis"] == "Leading and trailing."

    def test_generate_content_called_exactly_once(self):
        mock_model = self._fake_model("ok")
        with patch("google.generativeai.GenerativeModel") as MockModel, \
             patch("google.generativeai.configure"):
            MockModel.return_value = mock_model
            state  = {"company": "Y", "role": "SDE", "research_data": ["data"]}
            synthesize_node(state)

        mock_model.generate_content.assert_called_once()


# ================================================================
#  GROUP 4 -- Pydantic model validation (pure Python)
# ================================================================

class TestPydanticModels:
    """
    Pydantic validates data at construction time.
    No mocking needed -- these are pure Python data classes.
    """

    def test_company_profile_stores_all_fields(self):
        cp = CompanyProfile(name="Google", founded="1998",
                            hq="Mountain View", focus="DSA")
        assert cp.name    == "Google"
        assert cp.founded == "1998"
        assert cp.hq      == "Mountain View"
        assert cp.focus   == "DSA"

    def test_question_easy_difficulty(self):
        q = Question(text="What is a BST?", difficulty="Easy")
        assert q.difficulty == "Easy"

    def test_question_hard_difficulty(self):
        q = Question(text="Design a distributed cache.", difficulty="Hard")
        assert q.text.startswith("Design")

    def test_feedback_score_at_max(self):
        fb = FeedbackReport(score=10, strengths=["great"], improvements=[])
        assert fb.score == 10

    def test_feedback_score_at_min(self):
        fb = FeedbackReport(score=0, strengths=[], improvements=["everything"])
        assert fb.score == 0

    def test_feedback_score_above_10_raises(self):
        with pytest.raises(Exception):
            FeedbackReport(score=11, strengths=[], improvements=[])

    def test_feedback_score_negative_raises(self):
        with pytest.raises(Exception):
            FeedbackReport(score=-1, strengths=[], improvements=[])

    def test_feedback_lists_populated(self):
        fb = FeedbackReport(
            score=7,
            strengths=["clear thinking", "good examples"],
            improvements=["be more concise"],
        )
        assert len(fb.strengths) == 2
        assert "concise" in fb.improvements[0]


# ================================================================
#  GROUP 5 -- Full pipeline (both APIs mocked end-to-end)
# ================================================================

class TestFullPipeline:
    """
    Chain research_node -> route_after_research -> synthesize_node
    with Tavily AND Gemini both mocked.

    This is what a real integration unit test looks like:
      - No API keys needed
      - Deterministic results
      - Runs in milliseconds
    """

    def test_full_happy_path(self):
        """3 snippets -> 'enough' route -> synthesis produced."""
        fake_snippets = [
            {"content": "Atlassian: system design heavy."},
            {"content": "Two coding rounds, one design round."},
            {"content": "Behavioral round with STAR method."},
        ]
        expected_synthesis = "Atlassian emphasizes system design and collaboration."

        with patch("tavily.TavilyClient") as MockTavily, \
             patch("google.generativeai.GenerativeModel") as MockModel, \
             patch("google.generativeai.configure"):

            # Set up Tavily mock
            MockTavily.return_value.search.return_value = {"results": fake_snippets}

            # Set up Gemini mock
            mock_resp = MagicMock()
            mock_resp.text = expected_synthesis
            MockModel.return_value.generate_content.return_value = mock_resp

            # Run pipeline
            state = {"company": "Atlassian", "role": "SDE",
                     "research_data": [], "retry_count": 0}
            state.update(research_node(state))

            route = route_after_research(state)
            assert route == "enough"      # enough data, proceed

            state.update(synthesize_node(state))

        assert len(state["research_data"]) == 3
        assert state["synthesis"] == expected_synthesis
        assert state["retry_count"] == 1

    def test_insufficient_data_stays_in_retry(self):
        """Only 1 snippet -> router sends back to retry."""
        with patch("tavily.TavilyClient") as MockTavily:
            MockTavily.return_value.search.return_value = {"results": [
                {"content": "Only one result found."}
            ]}
            state = {"company": "SmallCo", "role": "SDE",
                     "research_data": [], "retry_count": 0}
            state.update(research_node(state))

        route = route_after_research(state)
        assert route == "retry"

    def test_error_after_exhausted_retries(self):
        """0 snippets + retry_count >= 2 -> 'error' route."""
        with patch("tavily.TavilyClient") as MockTavily:
            MockTavily.return_value.search.return_value = {"results": []}
            state = {"company": "NoData", "role": "SDE",
                     "research_data": [], "retry_count": 1}
            state.update(research_node(state))   # retry_count becomes 2

        route = route_after_research(state)
        assert route == "error"


# ================================================================
#  MAIN -- run with python directly (not just pytest)
# ================================================================
if __name__ == "__main__":
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT)
    )
    sys.exit(result.returncode)


# ── DELIBERATE BREAKING TEST (CI demo) ──────────────────────────
def test_BREAKING_this_will_fail():
    """This test is intentionally broken to demonstrate CI failure."""
    assert 1 == 2, "BREAKING CHANGE: this commit is intentionally broken for CI demo"
