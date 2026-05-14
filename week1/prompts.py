import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"


def call_gemini(prompt: str, system: str = "") -> str:
    payload = {
        "system_instruction": {"parts": [{"text": system}]} if system else {},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    response = httpx.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


# ── 1. ZERO-SHOT ──────────────────────────────────────────────────────────────
# Just ask directly. No examples, no reasoning steps.
def zero_shot(company: str) -> str:
    prompt = f"What is the interview process at {company} for a fresher software engineer?"
    return call_gemini(prompt)


# ── 2. FEW-SHOT ───────────────────────────────────────────────────────────────
# Give examples of the format you want before the real question.
def few_shot(company: str) -> str:
    prompt = f"""Here are two examples of interview process summaries:

Company: TCS
Summary: 3 rounds — online test (aptitude + coding), technical interview (DSA, OOP, SQL), HR interview. Focus on C/Java basics and communication.

Company: Infosys
Summary: 3 rounds — InfyTQ online test, technical interview (programming concepts, puzzles), HR interview. Strong focus on Python and reasoning.

Now give me the same format for:
Company: {company}
Summary:"""
    return call_gemini(prompt)


# ── 3. CHAIN-OF-THOUGHT ───────────────────────────────────────────────────────
# Ask the model to reason step by step before giving the answer.
def chain_of_thought(company: str) -> str:
    prompt = f"""Think step by step about how to prepare for a fresher software engineer interview at {company}.

Step 1: What kind of company is {company} (product vs service, size, domain)?
Step 2: What does that tell us about their interview style?
Step 3: What specific topics should a fresher focus on?
Step 4: What is the final preparation plan?

Work through each step, then give the final plan."""
    return call_gemini(prompt)


# ── 4. STRUCTURED JSON OUTPUT ─────────────────────────────────────────────────
# Force the model to return valid JSON. Retry if parsing fails.
def get_company_profile(company: str, max_retries: int = 3) -> dict:
    system = "You are a JSON API. Respond only with valid JSON. No explanation, no markdown, no code fences."
    prompt = f"""Return a JSON object for {company} with exactly these fields:
{{
  "company": "string",
  "founded": "string",
  "hq": "string",
  "tech_stack": ["list", "of", "strings"],
  "known_for": "string",
  "typical_roles": ["list", "of", "strings"],
  "interview_difficulty": "easy | medium | hard"
}}"""

    for attempt in range(1, max_retries + 1):
        raw = call_gemini(prompt, system)
        # Strip markdown code fences if model adds them despite instructions
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"[Attempt {attempt}/{max_retries}] JSON parse failed: {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Failed to get valid JSON after {max_retries} attempts") from e


# ── MAIN: compare all three approaches ───────────────────────────────────────
if __name__ == "__main__":
    company = input("Enter company name: ").strip()

    print("\n" + "="*60)
    print("1. ZERO-SHOT")
    print("="*60)
    print(zero_shot(company))

    print("\n" + "="*60)
    print("2. FEW-SHOT")
    print("="*60)
    print(few_shot(company))

    print("\n" + "="*60)
    print("3. CHAIN-OF-THOUGHT")
    print("="*60)
    print(chain_of_thought(company))

    print("\n" + "="*60)
    print("4. STRUCTURED JSON OUTPUT")
    print("="*60)
    profile = get_company_profile(company)
    print(json.dumps(profile, indent=2))
