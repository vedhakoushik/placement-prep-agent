"""
src/utils.py — Shared Utilities  (Day 40)
==========================================
Consolidates every duplicated helper that appeared 3–5× across weeks 1–5:

  _gemini()   → appeared in day31, day33, day34-35, week4 files
  _search()   → appeared in day31, day33, day34-35
  _validate() → appeared inline in every file
  log_*       → scattered prints, now a real logger

Import from any week file:
    from src.utils import gemini, search, get_logger, validate_env

All functions:
  gemini(prompt, model, temperature) → str
  search(query, max_results)         → list[str]
  get_logger(name)                   → logging.Logger
  validate_env(raise_on_missing)     → dict[str, bool]
  extract_questions(text)            → list[str]
  build_metadata(raw_text)           → dict
  truncate(text, max_chars)          → str
"""

from __future__ import annotations

import io
import os
import re
import json
import logging
import sys
import time
import functools

# Force UTF-8 output on Windows (avoids UnicodeEncodeError for ✓ ✗ etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from typing   import Any, Callable, Optional
from pathlib  import Path

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  LOGGING  (extracted from day39_logging.py)
# ═══════════════════════════════════════════════════════════════
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        skip = {
            "args","created","exc_info","exc_text","filename","funcName",
            "levelname","levelno","lineno","message","module","msecs","msg",
            "name","pathname","process","processName","relativeCreated",
            "stack_info","taskName","thread","threadName",
        }
        payload = {
            "ts":    datetime.fromtimestamp(record.created, tz=timezone.utc)
                             .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg":   record.getMessage(),
            **{k: v for k, v in record.__dict__.items() if k not in skip},
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a named JSON-line logger. Call once per module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(_JsonFormatter())
        logger.addHandler(h)
    logger.setLevel(level)
    logger.propagate = False
    return logger


_log = get_logger("src.utils")


# ═══════════════════════════════════════════════════════════════
#  ENV VALIDATION  (extracted from day39_logging.py)
# ═══════════════════════════════════════════════════════════════
REQUIRED_KEYS = {
    "GEMINI_API_KEY": "https://aistudio.google.com/app/apikey",
    "TAVILY_API_KEY": "https://tavily.com",
}
OPTIONAL_KEYS = {
    "LANGSMITH_API_KEY": "https://smith.langchain.com",
    "LANGCHAIN_PROJECT": "default: placement-prep-agent",
}


class EnvValidationError(RuntimeError):
    pass


def validate_env(raise_on_missing: bool = True) -> dict[str, bool]:
    """Check required env vars. Raises EnvValidationError if missing."""
    missing, status = [], {}
    for key in REQUIRED_KEYS:
        ok = bool(os.getenv(key))
        status[key] = ok
        if not ok:
            missing.append(key)
    for key in OPTIONAL_KEYS:
        status[key] = bool(os.getenv(key))
    if missing and raise_on_missing:
        raise EnvValidationError(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Add them to your .env file."
        )
    return status


# ═══════════════════════════════════════════════════════════════
#  GEMINI WRAPPER  (consolidated from 5 duplicate _gemini() defs)
# ═══════════════════════════════════════════════════════════════
def gemini(
    prompt:      str,
    model:       str           = "gemini-2.5-flash",
    temperature: float         = 0.7,
    api_key:     Optional[str] = None,
) -> str:
    """
    Call Gemini and return the response text.

    Args:
        prompt:      The full prompt string.
        model:       Gemini model name. Default: gemini-2.5-flash.
        temperature: Sampling temperature (0.0–1.0).
        api_key:     Override GEMINI_API_KEY env var.

    Returns:
        Stripped response text.

    Raises:
        RuntimeError: If the API call fails after retries.

    Example:
        from src.utils import gemini
        answer = gemini("Explain two-pointer technique in 3 sentences.")
    """
    import google.generativeai as genai

    key = api_key or os.getenv("GEMINI_API_KEY", "")
    genai.configure(api_key=key)

    t0 = time.perf_counter()
    try:
        resp = genai.GenerativeModel(model).generate_content(
            prompt,
            generation_config={"temperature": temperature},
        )
        text = resp.text.strip()
        _log.info("gemini call ok",
                  extra={"model": model, "prompt_chars": len(prompt),
                         "response_chars": len(text),
                         "elapsed_s": round(time.perf_counter() - t0, 2)})
        return text
    except Exception as exc:
        _log.error("gemini call failed", exc_info=True,
                   extra={"model": model, "error": str(exc)})
        raise RuntimeError(f"Gemini error: {exc}") from exc


# ═══════════════════════════════════════════════════════════════
#  TAVILY SEARCH WRAPPER  (consolidated from 3 duplicate _search())
# ═══════════════════════════════════════════════════════════════
def search(
    query:       str,
    max_results: int           = 5,
    depth:       str           = "basic",
    api_key:     Optional[str] = None,
) -> list[str]:
    """
    Run a Tavily web search and return a list of content snippets.

    Args:
        query:       Search query string.
        max_results: Max number of results to return (1–10).
        depth:       "basic" (fast) or "advanced" (deeper, slower).
        api_key:     Override TAVILY_API_KEY env var.

    Returns:
        List of content strings, each up to 500 chars.

    Example:
        from src.utils import search
        snippets = search("Google SDE-2 interview experience DSA 2025")
    """
    from tavily import TavilyClient

    key = api_key or os.getenv("TAVILY_API_KEY", "")
    t0  = time.perf_counter()
    try:
        res = TavilyClient(api_key=key).search(
            query=query, max_results=max_results, search_depth=depth
        )
        snippets = [
            r.get("content", "")[:500]
            for r in res.get("results", [])
            if r.get("content")
        ]
        _log.info("search ok",
                  extra={"query": query[:60], "results": len(snippets),
                         "elapsed_s": round(time.perf_counter() - t0, 2)})
        return snippets
    except Exception as exc:
        _log.error("search failed", exc_info=True,
                   extra={"query": query[:60], "error": str(exc)})
        raise RuntimeError(f"Search error: {exc}") from exc


# ═══════════════════════════════════════════════════════════════
#  TEXT HELPERS
# ═══════════════════════════════════════════════════════════════
def truncate(text: str, max_chars: int = 2000) -> str:
    """Trim text to max_chars, appending '…' if cut."""
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"


def extract_questions(text: str) -> list[str]:
    """
    Parse a numbered question list from Gemini output.

    Handles formats:
      Q1. Question text [Easy]
      1. Question text
      1) Question text

    Returns a list of stripped question strings.
    """
    parts = re.split(r"\n(?=(?:Q?\d+[\.\)]|\d+[\.\)]))", text.strip())
    questions = [p.strip() for p in parts if p.strip()]
    return questions if questions else [text.strip()]


def build_metadata(raw_text: str) -> dict[str, str]:
    """
    Extract Founded / HQ / Type from a Gemini-formatted response like:
        Founded: 1998
        HQ: Mountain View
        Type: Product

    Returns {"founded": "1998", "hq": "Mountain View", "type": "Product"}
    with "?" for any missing field.
    """
    meta = {"founded": "?", "hq": "?", "type": "?"}
    for line in raw_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            key = k.strip().lower()
            if key in meta:
                meta[key] = v.strip()
    return meta


def difficulty_badge(question_text: str) -> str:
    """Return 'Easy', 'Medium', 'Hard', or '' based on bracket tag."""
    m = re.search(r"\[(Easy|Medium|Hard)\]", question_text, re.IGNORECASE)
    return m.group(1).capitalize() if m else ""


def clean_question(text: str) -> str:
    """Strip trailing [Easy/Medium/Hard] tag from a question string."""
    return re.sub(r"\s*\[(Easy|Medium|Hard)\]\s*$", "", text,
                  flags=re.IGNORECASE).strip()


# ═══════════════════════════════════════════════════════════════
#  @log_call DECORATOR  (from day39_logging.py)
# ═══════════════════════════════════════════════════════════════
def log_call(logger: Optional[logging.Logger] = None, *, level: int = logging.INFO):
    """
    Decorator: log function entry, exit, duration, and any exception.

    Usage:
        from src.utils import log_call, get_logger
        logger = get_logger(__name__)

        @log_call(logger)
        def my_node(state):
            ...
    """
    _logger = logger or _log

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            name = fn.__qualname__
            _logger.log(level, f"→ {name}",
                        extra={"fn": name, "event": "start"})
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = round(time.perf_counter() - t0, 3)
                _logger.log(level, f"← {name}",
                            extra={"fn": name, "event": "done",
                                   "elapsed_s": elapsed})
                return result
            except Exception as exc:
                elapsed = round(time.perf_counter() - t0, 3)
                _logger.error(f"✗ {name}: {exc}",
                              exc_info=True,
                              extra={"fn": name, "event": "error",
                                     "elapsed_s": elapsed})
                raise
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
#  QUICK SELF-TEST
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 58)
    print("  src/utils.py — Day 40 self-test")
    print("=" * 58)

    # Text helpers — no API keys needed
    print("\n  extract_questions:")
    sample = "Q1. Two Sum [Easy]\nQ2. LRU Cache [Medium]\nQ3. Hard tree problem [Hard]"
    for q in extract_questions(sample):
        badge = difficulty_badge(q)
        print(f"    [{badge:6}] {clean_question(q)}")

    print("\n  build_metadata:")
    raw = "Founded: 1998\nHQ: Mountain View\nType: Product"
    print(f"    {build_metadata(raw)}")

    print("\n  truncate:")
    long_text = "A" * 2100
    print(f"    {len(truncate(long_text))} chars (was {len(long_text)})")

    print("\n  validate_env (warn-only):")
    status = validate_env(raise_on_missing=False)
    for k, ok in status.items():
        print(f"    {'✓' if ok else '○'} {k}")

    print("\n  @log_call:")
    logger = get_logger("demo")

    @log_call(logger)
    def add(a, b):
        return a + b

    result = add(2, 3)
    print(f"    result = {result}")

    print("\n" + "=" * 58)
    print("  Day 40 done.")
    print("  Import from any file: from src.utils import gemini, search")
    print("=" * 58)
