"""
Day 48 — Logging & Error Monitoring
======================================
ONE concept: in production you can't sit next to the server watching it.
Structured logs tell you what happened; Sentry tells you when it breaks.

Two tools:
  1. Python logging (JSON format) — every search, every Gemini call,
     every error gets written to stdout. Railway/Render captures stdout
     and lets you search it in the Logs tab.

  2. Sentry — when the app crashes, Sentry emails you the full stack
     trace + the user's session context. Free tier handles ~5000 errors/month.

What to log per request:
  timestamp, company, which agents ran, tokens used, latency, any errors

JSON log format (one line per event):
  {"ts":"2026-05-30T10:23:11Z","level":"INFO","event":"chat_search",
   "company":"Google","tokens":1842,"latency_s":3.2,"sources":{"web":5,"gd":3,"jobs":4}}

Why JSON?
  - Machine-readable → grep, jq, Grafana, Datadog can parse it
  - Human-readable → you can still read it in the terminal
  - Structured → filter by any field without regex

Run:
  python week8/day48_logging.py   # demos the logger + shows Sentry setup
"""

import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
#  JSON LOGGER  (same pattern as src/utils.py)
# ═══════════════════════════════════════════════════════════════
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":     datetime.fromtimestamp(record.created, tz=timezone.utc)
                               .isoformat(timespec="milliseconds"),
            "level":  record.levelname,
            "event":  record.getMessage(),
        }
        # merge any extra fields
        skip = {"args","created","exc_info","exc_text","filename","funcName",
                "levelname","levelno","lineno","message","module","msecs","msg",
                "name","pathname","process","processName","relativeCreated",
                "stack_info","taskName","thread","threadName"}
        payload.update({k: v for k, v in record.__dict__.items() if k not in skip})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_app_logger(name: str = "placement-prep") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(_JsonFormatter())
        logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


# ═══════════════════════════════════════════════════════════════
#  SENTRY SETUP GUIDE
# ═══════════════════════════════════════════════════════════════
SENTRY_SETUP = """
  Sentry integration (free tier — ~5000 errors/month)
  ─────────────────────────────────────────────────────────────────

  1. Create account → sentry.io → New Project → Python
  2. pip install sentry-sdk (add to requirements.txt)
  3. In week5/day34_35_app.py, add at the top:

       import sentry_sdk
       sentry_sdk.init(
           dsn=os.getenv("SENTRY_DSN"),   # from Sentry project settings
           traces_sample_rate=0.1,         # trace 10% of requests
           environment="production",
       )

  4. Add SENTRY_DSN to Railway environment variables

  What Sentry captures automatically:
  - Full stack trace with local variables
  - User session context
  - Browser/OS info
  - Related errors grouped together
  - Email alert on first occurrence of each new error

  Test it:
  def trigger_error():
      division_by_zero = 1 / 0   # Sentry will email you within 30s
"""

WHAT_TO_LOG = """
  What to log in this app
  ─────────────────────────────────────────────────────────────────

  Event: chat_search
    company, role, query, sources_found (web/gd/jobs count), latency_s

  Event: gemini_call
    prompt_chars, response_chars, model, latency_s, tokens_estimated

  Event: tavily_search
    query, domain_filter, results_count, latency_s

  Event: rate_limit_hit
    session_id, daily_requests_used, limit

  Event: error
    event_type, error_message, traceback (captured by Sentry)
"""

INTERVIEW_QA = [
    ("Why structured (JSON) logging instead of print statements?",
     "JSON logs are machine-readable. You can pipe them to jq, Grafana, or "
     "CloudWatch and filter by any field — e.g., all requests where latency > 5s. "
     "Print statements are just strings with no structure."),

    ("What is Sentry and why use it?",
     "Sentry is an error tracking service. When your app throws an exception, "
     "Sentry captures the full stack trace, local variables, and user context, "
     "and emails you immediately. Without it, you'd only find out about crashes "
     "when users complain."),

    ("What is log level and why does it matter?",
     "DEBUG/INFO/WARNING/ERROR/CRITICAL. In production, log INFO and above. "
     "DEBUG logs every internal step — too noisy for prod. In local dev, DEBUG "
     "helps trace exactly what's happening. Setting the level prevents log floods."),

    ("How do you avoid logging sensitive data?",
     "Never log API keys, passwords, or full user inputs. Log only what you need: "
     "company name, latency, token counts. If you must log user input, hash it or "
     "truncate to first 20 characters."),
]


def demo_logger():
    print("\n  Logger demo — JSON output")
    print("  " + "─" * 50)

    log = get_app_logger()

    # Simulate a chat search event
    t0 = time.perf_counter()
    time.sleep(0.05)   # simulate work
    latency = round(time.perf_counter() - t0, 3)

    log.info("chat_search", extra={
        "company":    "Google",
        "role":       "SDE-2",
        "latency_s":  latency,
        "sources":    {"web": 5, "glassdoor": 3, "jobs": 4},
        "tokens_est": 1842,
    })

    log.info("gemini_call", extra={
        "model":       "gemini-2.5-flash",
        "prompt_chars": 2400,
        "resp_chars":   680,
        "latency_s":   2.1,
    })

    log.warning("rate_limit_hit", extra={
        "session_requests": 20,
        "daily_limit":      20,
    })

    try:
        raise ValueError("Intentional test error for Sentry demo")
    except ValueError:
        log.error("unhandled_exception", exc_info=True, extra={"component": "demo"})


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 48 — Logging & Error Monitoring")
    print("  Tools: Python JSON logging + Sentry")
    print("=" * 62)

    demo_logger()
    print(SENTRY_SETUP)
    print(WHAT_TO_LOG)

    print("  Interview Q&A")
    print("  " + "─" * 50)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")

    print("\n" + "=" * 62)
    print("  Key rules:")
    print("  1. Log everything that matters (latency, tokens, errors)")
    print("  2. Never log API keys or raw user passwords")
    print("  3. Use JSON format so logs are machine-searchable")
    print("  4. Sentry for exceptions; logging for normal flow")
    print("=" * 62)
