import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"

HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}


def call_claude(user_message: str) -> dict:
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "system": "You are a placement advisor helping engineering students prepare for tech company interviews in India.",
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }
    response = httpx.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    print("Claude API — raw HTTP (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        data = call_claude(user_input)

        # Uncomment the next line any time you want to see the raw API response
        # print(json.dumps(data, indent=2))

        reply = data["content"][0]["text"]
        input_tokens = data["usage"]["input_tokens"]
        output_tokens = data["usage"]["output_tokens"]
        stop_reason = data["stop_reason"]

        print(f"\nClaude: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | stop: {stop_reason}]\n")


if __name__ == "__main__":
    main()
