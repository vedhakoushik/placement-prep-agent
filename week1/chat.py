import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

SYSTEM_PROMPT = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def call_gemini(user_message: str) -> dict:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]}
        ],
    }
    response = httpx.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    print("Gemini API — raw HTTP (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        data = call_gemini(user_input)

        # Gemini field mapping (vs Anthropic):
        #   candidates[0].content.parts[0].text  →  content[0].text
        #   candidates[0].finishReason            →  stop_reason
        #   usageMetadata.promptTokenCount        →  usage.input_tokens
        #   usageMetadata.candidatesTokenCount    →  usage.output_tokens

        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens = data["usageMetadata"]["promptTokenCount"]
        output_tokens = data["usageMetadata"]["candidatesTokenCount"]
        stop_reason = data["candidates"][0]["finishReason"]

        print(f"\nGemini: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | stop: {stop_reason}]\n")


if __name__ == "__main__":
    main()
