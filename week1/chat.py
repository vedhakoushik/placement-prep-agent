from gemini_client import call, user_msg, token_stats

SYSTEM = "You are a placement advisor helping engineering students prepare for tech company interviews in India."


def main():
    print("Gemini API — raw HTTP (type 'quit' to exit)\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        data = call([user_msg(user_input)], system=SYSTEM, use_cache=False)

        reply         = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tokens, output_tokens = token_stats(data)
        stop_reason   = data["candidates"][0]["finishReason"]

        print(f"\nGemini: {reply}")
        print(f"\n[tokens: {input_tokens} in / {output_tokens} out | stop: {stop_reason}]\n")


if __name__ == "__main__":
    main()
