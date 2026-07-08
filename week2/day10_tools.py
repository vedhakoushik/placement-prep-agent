"""Day 10 — Tools & Function Calling
Claude receives a list of tool definitions, decides which to call, returns a structured
tool_call instead of text. Your code executes it, sends result back. Loop until done.
Task: 'What is 2847 * 39, and what day of the week is it today?' — Claude uses both tools."""

import os
from datetime import date
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",   # 1500 req/day free vs 2.5-flash's 20/day
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,              # 0 = deterministic for tool calls
    max_output_tokens=500,
)


# ── tools ──────────────────────────────────────────────────────
# @tool: registers function + docstring as a tool definition Claude can read

@tool
def get_current_date() -> str:
    """Returns today's date and the day of the week."""
    today = date.today()
    return f"{today.strftime('%A, %B %d, %Y')}"

@tool
def calculate(expression: str) -> str:
    """Evaluates a basic math expression and returns the numeric result.
    Example expressions: '2847 * 39', '100 / 4', '2 ** 10'"""
    try:
        result = eval(expression, {"__builtins__": {}})     # no builtins = safe eval
        return str(result)
    except Exception as e:
        return f"Error: {e}"

ALL_TOOLS     = [get_current_date, calculate]
TOOLS_MAP     = {t.name: t for t in ALL_TOOLS}


# ── manual tool loop ───────────────────────────────────────────
# this is what AgentExecutor does internally — building it manually shows how it works
def run_with_tools(question: str) -> str:
    divider(f"Q: {question}")

    llm_with_tools = llm.bind_tools(ALL_TOOLS)      # send tool definitions to Claude
    messages = [HumanMessage(content=question)]

    response = llm_with_tools.invoke(messages)
    rounds   = 0

    while response.tool_calls:                      # Claude wants to call a tool
        rounds += 1
        print(f"\n  Round {rounds} — Claude called {len(response.tool_calls)} tool(s):")
        messages.append(response)                   # add Claude's tool_call response

        for call in response.tool_calls:
            fn     = TOOLS_MAP.get(call["name"])
            result = fn.invoke(call["args"]) if fn else "Tool not found."
            print(f"    → {call['name']}({call['args']})")
            print(f"    ← {result}")
            # ToolMessage: links result back to the specific call via tool_call_id
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

        response = llm_with_tools.invoke(messages)  # Claude reads results and replies

    answer = response.content
    print(f"\n  Final: {answer}")
    return answer


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 10 — Tools & Function Calling")
    print("  Claude receives tool definitions, decides to call them,")
    print("  returns tool_call objects, your code runs them, sends results back.\n")

    # task from the plan — Claude must call both tools
    run_with_tools("What is 2847 multiplied by 39, and what day of the week is it today?")

    # extra tests
    run_with_tools("Calculate 512 divided by 16.")
    run_with_tools("What is today's date?")
