"""
Day 39 -- Logging + .env Validation
======================================
ONE concept: structured logging replaces bare print() — every event has
a level, timestamp, and context that tools like LangSmith or Datadog can parse.

What is NEW today:
  1. logging.getLogger()    -- named logger per module, not root logger
  2. StructuredFormatter    -- JSON-lines output for machine parsing
  3. .env validator         -- checks all required keys exist before the app starts
  4. log_call decorator     -- wraps any function with entry/exit/duration logs
  5. audit_env()            -- structured report of what's set vs missing

Why this matters:
  - bare print() vanishes in production; logging survives process restart
  - JSON logs are grep-able, parseable by Datadog / CloudWatch / Loki
  - .env validation surfaces missing keys at startup, not mid-run
  - @log_call gives you a free timing + error log on every agent function

Run:
  python week6/day39_logging.py

No API calls. No keys needed to see the output.
"""

import os, sys, json, logging, time, traceback, functools
from datetime import datetime, timezone
from pathlib import Path
from typing   import Any, Callable, Optional
from dotenv   import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  1. STRUCTURED JSON FORMATTER
#  Each log line is a valid JSON object — easy to pipe into jq or
#  ship to any log aggregator.
# ═══════════════════════════════════════════════════════════════
class StructuredFormatter(logging.Formatter):
    """Emits log records as single-line JSON objects."""

    LEVEL_MAP = {
        logging.DEBUG:    "DEBUG",
        logging.INFO:     "INFO",
        logging.WARNING:  "WARNING",
        logging.ERROR:    "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts":      datetime.fromtimestamp(record.created, tz=timezone.utc)
                               .isoformat(timespec="milliseconds"),
            "level":   self.LEVEL_MAP.get(record.levelno, "INFO"),
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        # Merge any extra= fields passed by the caller
        for key, val in record.__dict__.items():
            if key not in (
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "taskName",
                "thread", "threadName",
            ):
                payload[key] = val

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Return a named logger with the StructuredFormatter attached.
    Call once per module:  logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False   # don't duplicate to root logger
    return logger


# ═══════════════════════════════════════════════════════════════
#  2. @log_call DECORATOR
#  Wraps any function: logs entry with args, exit with duration,
#  and exception details if the function raises.
# ═══════════════════════════════════════════════════════════════
def log_call(logger: logging.Logger, *, level: int = logging.INFO):
    """
    Decorator factory.

    Usage:
        logger = get_logger(__name__)

        @log_call(logger)
        def research_node(state):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = fn.__qualname__
            logger.log(level, f"→ {fn_name} start",
                       extra={"fn": fn_name, "event": "call_start"})
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = round(time.perf_counter() - t0, 3)
                logger.log(level, f"← {fn_name} done",
                           extra={"fn": fn_name, "event": "call_done",
                                  "elapsed_s": elapsed})
                return result
            except Exception as exc:
                elapsed = round(time.perf_counter() - t0, 3)
                logger.error(f"✗ {fn_name} raised {type(exc).__name__}",
                             exc_info=True,
                             extra={"fn": fn_name, "event": "call_error",
                                    "elapsed_s": elapsed,
                                    "error_type": type(exc).__name__})
                raise
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
#  3. .env VALIDATOR
#  Define required keys once. Call validate_env() at app startup.
# ═══════════════════════════════════════════════════════════════
REQUIRED_KEYS = {
    "GEMINI_API_KEY":  "Get free at https://aistudio.google.com/app/apikey",
    "TAVILY_API_KEY":  "Get free at https://tavily.com",
}

OPTIONAL_KEYS = {
    "LANGSMITH_API_KEY":  "Get free at https://smith.langchain.com",
    "LANGCHAIN_PROJECT":  "Default: placement-prep-agent",
}


class EnvValidationError(RuntimeError):
    """Raised when one or more required env vars are missing."""
    pass


def validate_env(
    required: Optional[dict] = None,
    optional: Optional[dict] = None,
    raise_on_missing: bool = True,
) -> dict[str, bool]:
    """
    Check that all required keys exist in os.environ.

    Returns a dict of {key: is_present} for every key checked.
    Raises EnvValidationError if raise_on_missing=True and any required key is absent.

    Usage at app startup:
        from week6.day39_logging import validate_env
        validate_env()   # raises if GEMINI_API_KEY or TAVILY_API_KEY missing
    """
    logger = get_logger("env.validator")
    required = required or REQUIRED_KEYS
    optional = optional or OPTIONAL_KEYS

    status: dict[str, bool] = {}
    missing: list[str]      = []

    for key, hint in required.items():
        present = bool(os.getenv(key))
        status[key] = present
        if present:
            masked = os.environ[key][:6] + "…"
            logger.info(f"✓ {key}", extra={"key": key, "status": "ok", "masked": masked})
        else:
            logger.error(f"✗ {key} MISSING — {hint}",
                         extra={"key": key, "status": "missing", "hint": hint})
            missing.append(key)

    for key, hint in optional.items():
        present = bool(os.getenv(key))
        status[key] = present
        lvl = logging.INFO if present else logging.WARNING
        label = "✓" if present else "○"
        logger.log(lvl, f"{label} {key} ({'set' if present else 'optional — not set'})",
                   extra={"key": key, "status": "ok" if present else "optional"})

    if missing and raise_on_missing:
        raise EnvValidationError(
            f"Missing required env vars: {', '.join(missing)}\n"
            f"Add them to your .env file and restart."
        )

    return status


def audit_env() -> None:
    """Pretty-print a human-readable env audit to stdout."""
    print("\n" + "=" * 58)
    print("  ENV AUDIT")
    print("=" * 58)

    categories = {
        "Required":  REQUIRED_KEYS,
        "Optional":  OPTIONAL_KEYS,
    }
    for category, keys in categories.items():
        print(f"\n  {category}:")
        for key, hint in keys.items():
            val = os.getenv(key, "")
            if val:
                masked = val[:6] + "••••" + val[-3:]
                print(f"    ✓  {key:<26} {masked}")
            else:
                print(f"    ✗  {key:<26} NOT SET — {hint}")
    print()


# ═══════════════════════════════════════════════════════════════
#  4. FILE HANDLER — persist logs to disk
#  Append to .logs/agent.jsonl; keep last 10 MB (RotatingFileHandler)
# ═══════════════════════════════════════════════════════════════
def add_file_handler(
    logger: logging.Logger,
    log_dir: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,   # 10 MB
    backup_count: int = 3,
) -> Path:
    """
    Attach a RotatingFileHandler to logger.
    Returns the path of the log file.

    Usage:
        logger = get_logger("agent")
        log_path = add_file_handler(logger)
        logger.info("App started", extra={"pid": os.getpid()})
    """
    from logging.handlers import RotatingFileHandler

    log_dir = log_dir or (ROOT / ".logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "agent.jsonl"

    fh = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setFormatter(StructuredFormatter())
    logger.addHandler(fh)
    return log_path


# ═══════════════════════════════════════════════════════════════
#  DEMO
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 58)
    print("  Day 39 -- Logging + .env Validation")
    print("=" * 58)

    # ── 1. Env audit ────────────────────────────────────────────
    audit_env()

    # ── 2. Validate (warn only, don't raise — demo mode) ────────
    try:
        validate_env(raise_on_missing=False)
    except EnvValidationError as e:
        print(f"\n  ERROR: {e}")

    # ── 3. Named logger with JSON output ────────────────────────
    print("\n  Structured JSON log lines:")
    print("-" * 58)
    logger = get_logger("agent.research")
    logger.info("Research session started",
                extra={"company": "Google", "role": "SDE-2", "focus": "DSA"})
    logger.warning("Rate limit approaching",
                   extra={"remaining_calls": 3, "limit": 60})

    # ── 4. @log_call decorator ──────────────────────────────────
    print("\n  @log_call decorator demo:")
    print("-" * 58)

    @log_call(logger)
    def fake_research(company: str, role: str) -> list:
        time.sleep(0.05)   # simulate work
        return ["snippet 1", "snippet 2"]

    @log_call(logger)
    def fake_fail(x: int) -> None:
        raise ValueError(f"bad input: {x}")

    fake_research("Google", "SDE-2")

    try:
        fake_fail(42)
    except ValueError:
        pass   # error already logged by decorator

    # ── 5. File handler ─────────────────────────────────────────
    log_path = add_file_handler(logger)
    logger.info("Log file attached", extra={"path": str(log_path)})
    print(f"\n  Logs also written to: {log_path}")

    print("\n" + "=" * 58)
    print("  Day 39 done.")
    print("  get_logger()       -> named logger, JSON lines to stdout")
    print("  @log_call(logger)  -> auto entry/exit/error/timing")
    print("  validate_env()     -> raises at startup if keys missing")
    print("  add_file_handler() -> rotating .jsonl file on disk")
    print("=" * 58)
