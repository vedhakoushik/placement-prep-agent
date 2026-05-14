import httpx
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SYSTEM_PROMPT = """You are a strict but encouraging technical interviewer for top tech companies in India.

Your behaviour:
- Ask ONE question at a time. Wait for the candidate's answer before asking the next.
- After each answer, give brief feedback (2-3 lines): what was good, what was missing.
- Do not reveal all questions upfront.
- Be professional but supportive — this is a learning environment.
- Keep your questions and feedback concise and specific to the company and role given."""


def call_gemini(messages: list, retries: int = 4) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,
    }
    for attempt in range(1, retries + 1):
        response = httpx.post(API_URL, json=payload, timeout=30)
        if response.status_code == 429:
            wait = attempt * 15          # 15s → 30s → 45s → 60s
            print(f"\n  [Rate limited — waiting {wait}s before retry {attempt}/{retries}...]")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError("API still rate-limiting after all retries. Wait a minute and try again.")


def get_ideal_answer(company: str, role: str, question: str) -> str:
    """Generate a model answer for the question — shown only if candidate requests it."""
    prompt = (f"A candidate for {role} at {company} was asked: \"{question}\"\n\n"
              f"Give a strong, concise model answer (8-10 lines) that would impress an interviewer. "
              f"Format it clearly with key points.")
    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    return call_gemini(messages)


def get_performance_summary(company: str, role: str, qa_pairs: list) -> dict:
    qa_text = "\n\n".join(
        f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}\nFeedback: {qa['feedback']}"
        for i, qa in enumerate(qa_pairs)
    )
    prompt = f"""You evaluated a mock interview for {role} at {company}.
Here is the full Q&A with your feedback:

{qa_text}

Return ONLY a JSON object with this exact structure:
{{
  "company": "{company}",
  "role": "{role}",
  "overall_score": <integer 1-10>,
  "strengths": ["list of 2-3 strong points"],
  "improvements": ["list of 2-3 areas to work on"],
  "topic_scores": {{"DSA": <1-10>, "OOP": <1-10>, "HR": <1-10>}},
  "recommendation": "Ready / Needs more prep / Not ready"
}}"""

    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    raw = call_gemini(messages)
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def save_session(company: str, role: str, qa_pairs: list, summary: dict):
    os.makedirs("data/sessions", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"data/sessions/interview_{company.lower()}_{timestamp}.json"
    data = {
        "timestamp": timestamp,
        "company": company,
        "role": role,
        "qa_pairs": qa_pairs,
        "summary": summary,
    }
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    return filepath


def divider(char="─", width=62):
    print(char * width)


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              Terminal Interview Coach  🎯                    ║
║         Powered by Gemini 2.5 Flash + raw httpx              ║
╚══════════════════════════════════════════════════════════════╝
  After each answer you can type:
    's' → skip (move to next question)
    'a' → see the ideal answer for that question
    anything else → your actual answer
""")

    company = input("  Company you're preparing for: ").strip()
    role    = input("  Role (e.g. SDE-1, Data Analyst): ").strip()
    print()
    divider()

    messages = []
    opening = (f"Start the mock interview for {role} at {company}. "
               f"Greet the candidate warmly, then ask your first question.")
    messages.append({"role": "user", "parts": [{"text": opening}]})

    reply = call_gemini(messages)
    messages.append({"role": "model", "parts": [{"text": reply}]})
    print(f"\nInterviewer: {reply}\n")

    # Extract the first question from the opening reply
    current_question = reply

    qa_pairs = []
    total_questions = 5

    for q_num in range(1, total_questions + 1):
        divider("·")
        print(f"  Question {q_num} of {total_questions}  [ type 'a' for ideal answer | 's' to skip ]")
        divider("·")

        answer = input("\nYou: ").strip()

        # ── SHOW IDEAL ANSWER ──────────────────────────────────────
        if answer.lower() == "a":
            print("\n  Fetching ideal answer...\n")
            ideal = get_ideal_answer(company, role, current_question)
            divider("·")
            print(f"  IDEAL ANSWER:\n")
            print(f"  {ideal.replace(chr(10), chr(10) + '  ')}")
            divider("·")
            print("\n  Now give your own answer (or 's' to skip):\n")
            answer = input("You: ").strip()

        # ── SKIP ───────────────────────────────────────────────────
        if answer.lower() == "s" or not answer:
            answer = "(skipped)"

        # ── GET FEEDBACK + NEXT QUESTION ──────────────────────────
        if q_num < total_questions:
            prompt = (f"The candidate answered: \"{answer}\"\n"
                      f"Give brief feedback on that answer, then ask question {q_num + 1} of {total_questions}.")
        else:
            prompt = (f"The candidate answered: \"{answer}\"\n"
                      f"Give brief feedback on that final answer, then wrap up the interview professionally.")

        messages.append({"role": "user", "parts": [{"text": prompt}]})
        reply = call_gemini(messages)
        messages.append({"role": "model", "parts": [{"text": reply}]})

        print(f"\nInterviewer: {reply}\n")

        # Track the next question (last thing the interviewer said)
        current_question = reply

        qa_pairs.append({
            "question": f"Question {q_num}",
            "answer": answer,
            "feedback": reply,
        })

    # ── PERFORMANCE SUMMARY ────────────────────────────────────────
    divider()
    print("\n  Generating your performance report...\n")
    try:
        summary = get_performance_summary(company, role, qa_pairs)

        divider("═")
        print("  PERFORMANCE SUMMARY")
        divider("═")
        print(f"  Company    : {summary['company']}")
        print(f"  Role       : {summary['role']}")
        print(f"  Score      : {summary['overall_score']} / 10")
        print(f"  Verdict    : {summary['recommendation']}")
        print()
        print("  Strengths:")
        for s in summary["strengths"]:
            print(f"    ✓ {s}")
        print()
        print("  Areas to improve:")
        for i in summary["improvements"]:
            print(f"    → {i}")
        print()
        print("  Topic scores:")
        for topic, score in summary["topic_scores"].items():
            bar = "█" * score + "░" * (10 - score)
            print(f"    {topic:<6} {bar} {score}/10")
        divider("═")

    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [Could not parse summary: {e}]")
        summary = {}

    filepath = save_session(company, role, qa_pairs, summary)
    print(f"\n  Session saved → {filepath}\n")


if __name__ == "__main__":
    main()
