"""
Day 32 -- Error Handling & Retries
=====================================
ONE concept: wrap every API call with tenacity exponential backoff.

What is NEW today:
  1. tenacity @retry decorator   -- retry up to 3x with 1s->2s->4s waits
  2. Error log entry             -- timestamp, node name, attempt, message
  3. Failure simulation          -- first 2 calls to Gemini deliberately raise
  4. try/except in every node    -- errors go to state["errors"], never crash

Nothing else is new. The graph is a single research node.
The whole point is watching the retry fire and the logs being generated.

Install: pip install tenacity
"""

import os, time, logging
from datetime import datetime
from typing import TypedDict, List
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_exception_type,
)

load_dotenv()

# ── Logger for tenacity ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="  [%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("day32")


# ═══════════════════════════════════════════════════════════════
#  ERROR LOG ENTRY
# ═══════════════════════════════════════════════════════════════
class ErrorEntry:
    def __init__(self, node: str, attempt: int, message: str):
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.node      = node
        self.attempt   = attempt
        self.message   = str(message)[:120]

    def __str__(self):
        return f"[{self.timestamp}] node={self.node} attempt={self.attempt} err={self.message}"


# ═══════════════════════════════════════════════════════════════
#  FAILURE SIMULATOR
#  Raises on the first N calls to a given function, then succeeds.
# ═══════════════════════════════════════════════════════════════
class FailSimulator:
    def __init__(self, fail_count: int):
        self.fail_count = fail_count
        self.calls      = 0

    def check(self, node_name: str):
        self.calls += 1
        if self.calls <= self.fail_count:
            msg = f"Simulated API failure (call #{self.calls})"
            logger.warning(f"    SIMULATED FAIL: {msg}")
            raise RuntimeError(msg)


# One shared simulator: fails on calls 1 and 2, succeeds from call 3
simulator = FailSimulator(fail_count=2)


# ═══════════════════════════════════════════════════════════════
#  TENACITY-WRAPPED GEMINI CALL
# ═══════════════════════════════════════════════════════════════
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def call_gemini(prompt: str, node_name: str = "unknown") -> str:
    """
    Calls Gemini. If the simulator fires (or a real API error occurs),
    tenacity waits and retries up to 3 times.

    Backoff schedule:
      Attempt 1 fails -> wait 1s
      Attempt 2 fails -> wait 2s
      Attempt 3 fails -> raises (reraise=True)
    """
    # Check simulator first (simulates first 2 calls failing)
    simulator.check(node_name)

    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp  = model.generate_content(prompt)
    return resp.text.strip()


# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════
class ResearchState(TypedDict):
    company:    str
    role:       str
    synthesis:  str
    error_log:  List[str]   # formatted ErrorEntry strings
    errors:     List[str]


# ═══════════════════════════════════════════════════════════════
#  NODE WITH FULL ERROR HANDLING
# ═══════════════════════════════════════════════════════════════
def synthesize_node(state: ResearchState) -> dict:
    """
    Calls Gemini via call_gemini() which retries on failure.
    Logs every failure to state["error_log"].
    If all 3 attempts fail, catches the final exception and returns gracefully.
    """
    node  = "synthesize_node"
    logs  = list(state.get("error_log", []))
    errs  = list(state.get("errors", []))

    print(f"\n[{node}] Calling Gemini (simulator will fail first 2 attempts)")

    try:
        # tenacity handles the retries internally
        # Each failed attempt triggers before_sleep_log + wait
        result = call_gemini(
            f"Summarize {state['company']} {state['role']} interview in 80 words.",
            node_name=node,
        )
        print(f"  -> SUCCESS after simulator passed | {len(result)} chars")
        return {"synthesis": result, "error_log": logs}

    except Exception as e:
        # All 3 tenacity attempts exhausted
        entry = ErrorEntry(node=node, attempt=3, message=str(e))
        logs.append(str(entry))
        errs.append(str(e))
        print(f"  -> ALL RETRIES EXHAUSTED: {e}")
        return {"synthesis": "failed", "error_log": logs, "errors": errs}


# ═══════════════════════════════════════════════════════════════
#  GRAPH
# ═══════════════════════════════════════════════════════════════
def build_graph():
    from langgraph.graph import StateGraph, START, END
    b = StateGraph(ResearchState)
    b.add_node("synthesize_node", synthesize_node)
    b.add_edge(START, "synthesize_node")
    b.add_edge("synthesize_node", END)
    return b.compile()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import subprocess, sys
    try:
        import tenacity
    except ImportError:
        print("Installing tenacity...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tenacity", "-q"])
        import tenacity

    print("=" * 60)
    print("  Day 32 -- Error Handling & Retries")
    print("  NEW: @retry with exponential backoff + error_log in state")
    print("=" * 60)
    print()
    print("  Retry config: 3 attempts | backoff: 1s -> 2s -> 4s")
    print("  Simulator:    calls 1 and 2 raise RuntimeError")
    print("                call 3 passes through to Gemini")
    print()

    graph = build_graph()

    state: ResearchState = {
        "company":   "Google",
        "role":      "Software Engineer",
        "synthesis": "",
        "error_log": [],
        "errors":    [],
    }

    final = dict(state)
    for event in graph.stream(state, stream_mode="updates"):
        for node_name, delta in event.items():
            final.update(delta)

    print("\n" + "=" * 60)
    print("  RESULT")
    print("=" * 60)
    print(f"\n  Synthesis : {final.get('synthesis','')[:200]}")
    print(f"\n  Error log ({len(final.get('error_log',[]))} entries):")
    for entry in final.get("error_log", []):
        print(f"    {entry}")
    if final.get("errors"):
        print(f"\n  Unrecovered errors: {final['errors']}")

    print("\n" + "=" * 60)
    print("  Day 32 done.")
    print("  @retry wraps the API call. tenacity handles wait + retry count.")
    print("  Nodes catch the final exception and log it -- never crash.")
    print("=" * 60)
