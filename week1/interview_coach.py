import json
import os
from datetime import datetime
from gemini_client import call_text, user_msg, model_msg

SYSTEM = """You are a strict but encouraging technical interviewer for top tech companies in India.

Your behaviour:
- Ask ONE question at a time. Wait for the candidate's answer before asking the next.
- After each answer, give brief feedback (2-3 lines): what was good, what was missing.
- Do not reveal all questions upfront.
- Be professional but supportive — this is a learning environment.
- Keep your questions and feedback concise and specific to the company and role given."""


def get_ideal_answer(company: str, role: str, question: str) -> str:
    prompt = (f"A candidate for {role} at {company} was asked:\n\"{question}\"\n\n"
              f"Give a strong, concise model answer (8-10 lines) that would impress an interviewer. "
              f"Format it clearly with key points.")
    return call_text([user_msg(prompt)])


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

    raw     = call_text([user_msg(prompt)])
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def save_session(company: str, role: str, qa_pairs: list, summary: dict) -> str:
    os.makedirs("data/sessions", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath  = f"data/sessions/interview_{company.lower()}_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump({"timestamp": timestamp, "company": company,
                   "role": role, "qa_pairs": qa_pairs, "summary": summary}, f, indent=2)
    return filepath


def divider(char="─", width=62):
    print(char * width)


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              Terminal Interview Coach  🎯                    ║
║         Powered by Gemini 2.5 Flash + raw httpx              ║
╚══════════════════════════════════════════════════════════════╝
  After each answer:
    'a' → see the ideal answer first, then give your own
    's' → skip this question
    anything else → treated as your answer
""")

    company = input("  Company you're preparing for: ").strip()
    role    = input("  Role (e.g. SDE-1, Data Analyst): ").strip()
    print()
    divider()

    messages = []
    opening  = (f"Start the mock interview for {role} at {company}. "
                f"Greet the candidate warmly, then ask your first question.")
    messages.append(user_msg(opening))

    reply = call_text(messages, system=SYSTEM)
    messages.append(model_msg(reply))
    print(f"\nInterviewer: {reply}\n")

    current_question = reply
    qa_pairs         = []
    total_questions  = 5

    for q_num in range(1, total_questions + 1):
        divider("·")
        print(f"  Question {q_num} of {total_questions}  [ 'a' = ideal answer | 's' = skip ]")
        divider("·")

        answer = input("\nYou: ").strip()

        # Show ideal answer if requested
        if answer.lower() == "a":
            print("\n  Fetching ideal answer...\n")
            ideal = get_ideal_answer(company, role, current_question)
            divider("·")
            print("  IDEAL ANSWER:\n")
            print("  " + ideal.replace("\n", "\n  "))
            divider("·")
            print("\n  Now give your own answer (or 's' to skip):\n")
            answer = input("You: ").strip()

        if answer.lower() == "s" or not answer:
            answer = "(skipped)"

        if q_num < total_questions:
            prompt = (f"The candidate answered: \"{answer}\"\n"
                      f"Give brief feedback on that answer, then ask question {q_num + 1} of {total_questions}.")
        else:
            prompt = (f"The candidate answered: \"{answer}\"\n"
                      f"Give brief feedback on that final answer, then wrap up the interview professionally.")

        messages.append(user_msg(prompt))
        reply = call_text(messages, system=SYSTEM)
        messages.append(model_msg(reply))

        print(f"\nInterviewer: {reply}\n")

        current_question = reply
        qa_pairs.append({"question": f"Question {q_num}", "answer": answer, "feedback": reply})

    # Performance summary
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
