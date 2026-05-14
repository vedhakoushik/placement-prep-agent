from gemini_client import call, call_text, user_msg

SYSTEM = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def main():
    print("Gemini API — raw HTTP (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        data = call([user_msg(user_input)], system=SYSTEM)

        # Full response structure — uncomment to inspect:
        # import json; print(json.dumps(data, indent=2))

        reply        = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens = data["usageMetadata"]["promptTokenCount"]
        output_tokens = data["usageMetadata"]["candidatesTokenCount"]
        stop_reason  = data["candidates"][0]["finishReason"]

        print(f"\nGemini: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | stop: {stop_reason}]\n")


if __name__ == "__main__":
    main()
