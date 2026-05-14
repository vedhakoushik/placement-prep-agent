import httpx
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"

HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

SYSTEM_PROMPT = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def call_claude(messages: list) -> dict:
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,       # full history sent every time
    }
    response = httpx.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def save_session(messages: list):
    os.makedirs("data/sessions", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"data/sessions/session_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump({"session": timestamp, "messages": messages}, f, indent=2)
    print(f"\n[Session saved to {filepath}]")


def main():
    print("Multi-turn conversation with Claude (type 'quit' to exit)\n")
    print(f"System: {SYSTEM_PROMPT}\n")

    messages = []   # this list grows with every turn — Claude's "memory"

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            save_session(messages)
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        data = call_claude(messages)

        reply = data["content"][0]["text"]
        input_tokens = data["usage"]["input_tokens"]
        output_tokens = data["usage"]["output_tokens"]

        messages.append({"role": "assistant", "content": reply})

        print(f"\nClaude: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | turns: {len(messages) // 2}]\n")


if __name__ == "__main__":
    main()
