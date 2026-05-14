import json
import os
from datetime import datetime
from gemini_client import call, user_msg, model_msg

SYSTEM = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def save_session(messages: list):
    os.makedirs("data/sessions", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"data/sessions/session_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump({"session": timestamp, "messages": messages}, f, indent=2)
    print(f"\n[Session saved → {filepath}]")


def main():
    print("Multi-turn conversation with Gemini (type 'quit' to exit)\n")
    print(f"System: {SYSTEM}\n")

    messages = []   # grows every turn — this list IS the memory

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            save_session(messages)
            break
        if not user_input:
            continue

        messages.append(user_msg(user_input))
        data = call(messages, system=SYSTEM)

        reply         = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens  = data["usageMetadata"]["promptTokenCount"]
        output_tokens = data["usageMetadata"]["candidatesTokenCount"]

        messages.append(model_msg(reply))

        print(f"\nGemini: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | turns: {len(messages) // 2}]\n")


if __name__ == "__main__":
    main()
