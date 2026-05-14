import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SYSTEM_PROMPT = "You are a placement advisor helping engineering students prepare for tech company interviews in India."

# Gemini 2.5 Flash pricing (per 1K tokens)
COST_PER_1K_INPUT = 0.00015
COST_PER_1K_OUTPUT = 0.00060
CONTEXT_WINDOW = 1_048_576


def call_gemini(messages: list) -> dict:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,
    }
    response = httpx.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000 * COST_PER_1K_INPUT) + (output_tokens / 1000 * COST_PER_1K_OUTPUT)


def context_percent(total_tokens: int) -> float:
    return (total_tokens / CONTEXT_WINDOW) * 100


def print_stats(input_tokens: int, output_tokens: int, session_cost: float, turn: int):
    total_tokens = input_tokens + output_tokens
    pct = context_percent(input_tokens)  # input = full history sent = context used
    cost_this_turn = calculate_cost(input_tokens, output_tokens)

    warning = " ⚠️  APPROACHING LIMIT" if pct >= 80 else ""
    print(f"\n[turn {turn} | in: {input_tokens} | out: {output_tokens} | "
          f"cost: ${cost_this_turn:.5f} | session: ${session_cost:.5f} | "
          f"context: {pct:.2f}%{warning}]")


def main():
    print(f"Token Tracker Chat — model: {MODEL}")
    print(f"Context window: {CONTEXT_WINDOW:,} tokens | type 'quit' to exit\n")

    messages = []
    session_cost = 0.0
    turn = 0

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            print(f"\n── Session Summary ──")
            print(f"Turns: {turn}")
            print(f"Total cost: ${session_cost:.5f}")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "parts": [{"text": user_input}]})
        data = call_gemini(messages)

        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens = data["usageMetadata"]["promptTokenCount"]
        output_tokens = data["usageMetadata"]["candidatesTokenCount"]

        messages.append({"role": "model", "parts": [{"text": reply}]})

        turn += 1
        session_cost += calculate_cost(input_tokens, output_tokens)
        print(f"\nGemini: {reply}")
        print_stats(input_tokens, output_tokens, session_cost, turn)
        print()


if __name__ == "__main__":
    main()
