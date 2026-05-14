import hashlib
import httpx
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

MODEL    = "gemini-2.5-flash"
_API_KEY = os.getenv("GEMINI_API_KEY")
_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={_API_KEY}"

# ── In-memory cache ────────────────────────────────────────────────────────────
# Stores (messages + system) → response so identical prompts never hit the API twice.
_cache: dict[str, dict] = {}

# ── Token budget ───────────────────────────────────────────────────────────────
# Cap output tokens per call — prevents runaway responses that waste your quota.
MAX_OUTPUT_TOKENS = 512

# ── Retry config ───────────────────────────────────────────────────────────────
# 3 retries, waits of 5s + 5s + 5s = 15s total maximum wait.
_RETRY_WAITS = [5, 5, 5]


def _cache_key(messages: list, system: str) -> str:
    raw = json.dumps({"messages": messages, "system": system}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def call(messages: list, system: str = "", use_cache: bool = True) -> dict:
    """
    Make a Gemini API call with:
    - Response caching (skip API if same prompt seen before)
    - Output token cap (MAX_OUTPUT_TOKENS)
    - 3 retries, 15s total wait on rate limit
    """
    key = _cache_key(messages, system)
    if use_cache and key in _cache:
        print("  [cache hit — no API call made]")
        return _cache[key]

    payload: dict = {
        "contents": messages,
        "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS},
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    for attempt, wait in enumerate(_RETRY_WAITS, start=1):
        response = httpx.post(_API_URL, json=payload, timeout=30)
        if response.status_code == 429:
            print(f"\n  [Rate limited — waiting {wait}s | attempt {attempt}/3]")
            time.sleep(wait)
            continue
        response.raise_for_status()
        data = response.json()
        if use_cache:
            _cache[key] = data      # store for future identical calls
        return data

    raise RuntimeError("Rate-limited after 3 retries (15s total). Wait 60s and try again.")


def call_text(messages: list, system: str = "", use_cache: bool = True) -> str:
    """Returns just the reply text string."""
    data = call(messages, system, use_cache)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def user_msg(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def model_msg(text: str) -> dict:
    return {"role": "model", "parts": [{"text": text}]}


def token_stats(data: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a response dict."""
    meta = data.get("usageMetadata", {})
    return meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)
