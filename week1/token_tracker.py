import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SYSTEM_PROMPT = "You are a placement advisor helping engineering students prepare for tech company interviews in India."

COST_PER_1K_INPUT  = 0.00015
COST_PER_1K_OUTPUT = 0.00060
CONTEXT_WINDOW     = 1_048_576


def call_gemini(messages: list) -> dict:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,
    }
    response = httpx.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def cost(input_tok: int, output_tok: int) -> float:
    return (input_tok / 1000 * COST_PER_1K_INPUT) + (output_tok / 1000 * COST_PER_1K_OUTPUT)


def progress_bar(pct: float, width: int = 30) -> str:
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def print_stats(input_tok: int, output_tok: int, session_cost: float, turn: int):
    turn_cost = cost(input_tok, output_tok)
    pct = (input_tok / CONTEXT_WINDOW) * 100
    bar = progress_bar(pct)
    warning = "  ⚠️  WARNING: 80%+ context used!" if pct >= 80 else ""

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │ turn {turn:<3} │ in: {input_tok:<7,} tokens │ out: {output_tok:<7,} tokens      │
  │ cost: ${turn_cost:.5f}  │ session total: ${session_cost:.5f}          │
  │ context: {pct:.3f}%  {bar} │{warning}
  └─────────────────────────────────────────────────────────┘""")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         Token Tracker Chat — gemini-2.5-flash                ║
║  Context window: 1,048,576 tokens  |  type 'quit' to exit    ║
╚══════════════════════════════════════════════════════════════╝
""")

    messages = []
    session_cost = 0.0
    turn = 0

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            print(f"""
── Session Summary ──────────────────────────────────────────
  Turns completed : {turn}
  Total cost      : ${session_cost:.5f}
  Avg cost/turn   : ${(session_cost / turn if turn else 0):.5f}
─────────────────────────────────────────────────────────────""")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "parts": [{"text": user_input}]})
        data = call_gemini(messages)

        reply       = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tok   = data["usageMetadata"]["promptTokenCount"]
        output_tok  = data["usageMetadata"]["candidatesTokenCount"]

        messages.append({"role": "model", "parts": [{"text": reply}]})

        turn += 1
        session_cost += cost(input_tok, output_tok)

        print(f"\nGemini: {reply}")
        print_stats(input_tok, output_tok, session_cost, turn)
        print()


if __name__ == "__main__":
    main()
