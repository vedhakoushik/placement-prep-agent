"""
Day 49 — Rate Limiting & Cost Control
=======================================
ONE concept: without limits, one excited user can burn your entire monthly
API budget in 10 minutes. Rate limiting protects you from surprise bills.

Two layers of protection:
  1. Per-session request limit — max N searches per browser session
  2. Token budget — track estimated tokens per session, warn at 80%, block at 100%

Token estimation (Gemini pricing as of 2026):
  gemini-2.5-flash: $0.00015 per 1K input tokens, $0.00060 per 1K output tokens
  A typical chat search ≈ 2500 input + 500 output ≈ 0.67 cents

Cost dashboard in the Streamlit sidebar:
  Requests today: 7 / 20
  Tokens used: 18,400 / 50,000
  Estimated cost: $0.014 / $0.038

What happens at the limit:
  → Friendly message: "Daily limit reached. Reopen the app tomorrow."
  → No crash, no 429 error shown to user, no API call wasted

Rate limiting patterns:
  Per-session:   st.session_state["request_count"] (resets on browser close)
  Per-day:       SQLite table with date + count (survives restarts)
  Per-IP:        Reverse proxy or middleware (complex, not needed here)

Run:
  python week8/day49_rate_limiting.py   # demos the rate limiter
"""

import io
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
#  CONSTANTS — match these in the main app
# ═══════════════════════════════════════════════════════════════
DAILY_REQUEST_LIMIT = 20          # max searches per day per session
TOKEN_LIMIT         = 50_000      # max tokens per day per session
WARN_AT_TOKENS      = 40_000      # show warning at 80%
COST_PER_1K_IN      = 0.00015    # gemini-2.5-flash input
COST_PER_1K_OUT     = 0.00060    # gemini-2.5-flash output
AVG_INPUT_TOKENS    = 2500        # average per chat request
AVG_OUTPUT_TOKENS   = 500


# ═══════════════════════════════════════════════════════════════
#  RATE LIMITER  (session-state based, demonstrated standalone)
# ═══════════════════════════════════════════════════════════════
class SessionRateLimiter:
    """
    In-memory rate limiter for a Streamlit session.
    In the app, session_state replaces self._state.
    """

    def __init__(self):
        self._state = {
            "request_count": 0,
            "token_count":   0,
            "date":          str(date.today()),
        }

    def _reset_if_new_day(self):
        today = str(date.today())
        if self._state["date"] != today:
            self._state = {"request_count": 0, "token_count": 0, "date": today}

    def check(self) -> tuple[bool, str]:
        """Returns (allowed, message). allowed=False means block the request."""
        self._reset_if_new_day()

        if self._state["request_count"] >= DAILY_REQUEST_LIMIT:
            return False, (
                f"⛔ Daily limit reached ({DAILY_REQUEST_LIMIT} searches/day). "
                "Refresh tomorrow or upgrade your API key."
            )

        if self._state["token_count"] >= TOKEN_LIMIT:
            return False, (
                f"⛔ Token budget exhausted ({TOKEN_LIMIT:,} tokens/day). "
                "Refresh tomorrow."
            )

        if self._state["token_count"] >= WARN_AT_TOKENS:
            return True, (
                f"⚠️ Approaching token limit "
                f"({self._state['token_count']:,} / {TOKEN_LIMIT:,} used)."
            )

        return True, ""

    def record(self, input_tokens: int = AVG_INPUT_TOKENS,
               output_tokens: int = AVG_OUTPUT_TOKENS):
        """Call after a successful API request."""
        self._state["request_count"] += 1
        self._state["token_count"]   += input_tokens + output_tokens

    def dashboard(self) -> dict:
        """Returns dict for the cost dashboard UI."""
        req   = self._state["request_count"]
        tok   = self._state["token_count"]
        cost  = (tok / 1000) * COST_PER_1K_IN   # rough estimate
        limit_cost = (TOKEN_LIMIT / 1000) * COST_PER_1K_IN
        return {
            "requests":    f"{req} / {DAILY_REQUEST_LIMIT}",
            "tokens":      f"{tok:,} / {TOKEN_LIMIT:,}",
            "cost_usd":    f"${cost:.4f} / ${limit_cost:.4f}",
            "pct_used":    round(tok / TOKEN_LIMIT * 100, 1),
        }


# ═══════════════════════════════════════════════════════════════
#  STREAMLIT INTEGRATION SNIPPET
# ═══════════════════════════════════════════════════════════════
STREAMLIT_SNIPPET = '''
  # Add to week5/day34_35_app.py — sidebar cost dashboard
  # ──────────────────────────────────────────────────────────────

  # In session_state initialisation:
  if "usage" not in st.session_state:
      st.session_state.usage = {"requests": 0, "tokens": 0, "date": str(date.today())}

  # In sidebar (before rendering pages):
  u = st.session_state.usage
  st.sidebar.markdown("### Usage today")
  st.sidebar.progress(min(u["tokens"] / 50_000, 1.0))
  st.sidebar.caption(
      f"Searches: {u['requests']} / 20  ·  "
      f"Tokens: {u['tokens']:,} / 50,000"
  )

  # Before every _chat_process() call:
  if u["requests"] >= 20:
      st.error("Daily limit reached. Come back tomorrow.")
      st.stop()

  # After every _chat_process() call:
  u["requests"] += 1
  u["tokens"]   += 3000  # estimated per request
'''

INTERVIEW_QA = [
    ("Why rate limit a free-tier app?",
     "The Gemini free tier gives 20 req/day. Without a limit in the app itself, "
     "a single session could hammer the API, hitting the quota and blocking every "
     "subsequent user. Rate limiting ensures fair use across all visitors."),

    ("How would you implement per-IP rate limiting?",
     "Use a Redis cache keyed by IP address with a TTL equal to the window (24h). "
     "On each request, INCR the key and check against the limit. This is often done "
     "at the reverse proxy level (nginx, Cloudflare) to avoid hitting the app at all."),

    ("What is token cost estimation and why is it only an estimate?",
     "Tokens are roughly 4 characters / 0.75 words in English. We multiply estimated "
     "token count by the model's price-per-1K-tokens. It's an estimate because the "
     "exact count depends on the model's tokeniser — we don't call the API just to count."),

    ("What happens when a user hits the rate limit?",
     "Show a friendly, specific message ('Daily limit reached, come back tomorrow') "
     "and call st.stop(). Never show a raw 429 error. The message should explain "
     "what limit was hit and when it resets."),
]


def demo_rate_limiter():
    print("\n  Rate limiter demo")
    print("  " + "─" * 50)

    rl = SessionRateLimiter()

    print("  Making 22 requests (limit is 20):")
    for i in range(1, 23):
        allowed, msg = rl.check()
        if not allowed:
            print(f"  Request {i:2d}: BLOCKED — {msg}")
            break
        rl.record()
        dash = rl.dashboard()
        status = f"✓  {dash['requests']} requests | {dash['tokens']} tokens | {dash['cost_usd']}"
        if msg:
            status += f" | {msg}"
        if i % 5 == 0 or i >= 18:
            print(f"  Request {i:2d}: {status}")

    print("\n  Dashboard output:")
    for k, v in rl.dashboard().items():
        print(f"    {k:<12} {v}")


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 49 — Rate Limiting & Cost Control")
    print(f"  Limit: {DAILY_REQUEST_LIMIT} requests/day | {TOKEN_LIMIT:,} tokens/day")
    print("=" * 62)

    demo_rate_limiter()

    print("\n  Streamlit integration snippet")
    print("  " + "─" * 50)
    print(STREAMLIT_SNIPPET)

    print("  Interview Q&A")
    print("  " + "─" * 50)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")

    print("\n" + "=" * 62)
    print("  Three rules for API cost control:")
    print("  1. Limit requests AND tokens — both matter")
    print("  2. Show the user their usage in the UI (transparency)")
    print("  3. Friendly message on limit hit — never a raw 429")
    print("=" * 62)
