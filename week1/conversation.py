import httpx
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.0-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SYSTEM_PROMPT = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def call_gemini(messages: list) -> dict:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": messages,   # full history sent every time — same concept as Anthropic
    }
    response = httpx.post(API_URL, json=payload, timeout=30)
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
    print("Multi-turn conversation with Gemini (type 'quit' to exit)\n")
    print(f"System: {SYSTEM_PROMPT}\n")

    # Gemini uses "model" for assistant role; Anthropic uses "assistant"
    # Everything else (appending history, sending full list) is identical
    messages = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            save_session(messages)
            break
        if not user_input:
            continue

        messages.append({"role": "user", "parts": [{"text": user_input}]})

        data = call_gemini(messages)

        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens = data["usageMetadata"]["promptTokenCount"]
        output_tokens = data["usageMetadata"]["candidatesTokenCount"]

        messages.append({"role": "model", "parts": [{"text": reply}]})

        print(f"\nGemini: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | turns: {len(messages) // 2}]\n")


if __name__ == "__main__":
    main()
