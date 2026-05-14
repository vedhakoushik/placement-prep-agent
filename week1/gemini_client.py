import httpx
import os
import time
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-2.5-flash"
_API_KEY = os.getenv("GEMINI_API_KEY")
_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={_API_KEY}"


def call(messages: list, system: str = "", retries: int = 4) -> dict:
    """Make a Gemini API call. Returns the full response dict."""
    payload = {"contents": messages}
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    for attempt in range(1, retries + 1):
        response = httpx.post(_API_URL, json=payload, timeout=30)
        if response.status_code == 429:
            wait = attempt * 15
            print(f"\n  [Rate limited — waiting {wait}s before retry {attempt}/{retries}...]")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()

    raise RuntimeError("Still rate-limited after all retries. Wait 60s and try again.")


def call_text(messages: list, system: str = "") -> str:
    """Convenience wrapper — returns just the reply text."""
    data = call(messages, system)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def user_msg(text: str) -> dict:
    """Build a Gemini user message dict."""
    return {"role": "user", "parts": [{"text": text}]}


def model_msg(text: str) -> dict:
    """Build a Gemini model message dict."""
    return {"role": "model", "parts": [{"text": text}]}
