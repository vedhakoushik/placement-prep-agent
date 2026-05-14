from gemini_client import call, user_msg, model_msg

SYSTEM = "You are a placement advisor helping engineering students prepare for tech company interviews in India."

COST_PER_1K_INPUT  = 0.00015
COST_PER_1K_OUTPUT = 0.00060
CONTEXT_WINDOW     = 1_048_576


def cost(input_tok: int, output_tok: int) -> float:
    return (input_tok / 1000 * COST_PER_1K_INPUT) + (output_tok / 1000 * COST_PER_1K_OUTPUT)


def progress_bar(pct: float, width: int = 30) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def print_stats(input_tok: int, output_tok: int, session_cost: float, turn: int):
    turn_cost = cost(input_tok, output_tok)
    pct       = (input_tok / CONTEXT_WINDOW) * 100
    bar       = progress_bar(pct)
    warning   = "  ⚠️  WARNING: 80%+ context used!" if pct >= 80 else ""

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

    messages     = []
    session_cost = 0.0
    turn         = 0

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            avg = session_cost / turn if turn else 0
            print(f"""
── Session Summary ──────────────────────────────────────────
  Turns completed : {turn}
  Total cost      : ${session_cost:.5f}
  Avg cost/turn   : ${avg:.5f}
─────────────────────────────────────────────────────────────""")
            break
        if not user_input:
            continue

        messages.append(user_msg(user_input))
        data = call(messages, system=SYSTEM)

        reply         = data["candidates"][0]["content"]["parts"][0]["text"]
        input_tok     = data["usageMetadata"]["promptTokenCount"]
        output_tok    = data["usageMetadata"]["candidatesTokenCount"]

        messages.append(model_msg(reply))

        turn         += 1
        session_cost += cost(input_tok, output_tok)

        print(f"\nGemini: {reply}")
        print_stats(input_tok, output_tok, session_cost, turn)
        print()


if __name__ == "__main__":
    main()
