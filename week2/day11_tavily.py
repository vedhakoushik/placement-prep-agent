"""Day 11 — Web Search with Tavily
TavilySearchResults used as a tool with bind_tools() + manual tool loop.
verbose prints every tool call and result so you can watch the agent think.
Task: research Infosys SDE-1 interview process — log every tool call."""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, ToolMessage

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",   # 1500 req/day free
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=1000,
)

# ── tool: tavily web search ────────────────────────────────────
tavily = TavilySearchResults(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=3,
)
tools     = [tavily]
tools_map = {t.name: t for t in tools}

llm_with_tools = llm.bind_tools(tools)   # send tool definitions to Gemini


# ── manual tool loop ───────────────────────────────────────────
# same pattern as day10 — bind_tools → invoke → check tool_calls → execute → repeat
def research(query: str) -> str:
    divider(f"Query: {query}")

    messages = [HumanMessage(content=query)]
    response = llm_with_tools.invoke(messages)
    rounds   = 0

    while response.tool_calls:
        rounds += 1
        print(f"\n  Round {rounds} — Gemini called {len(response.tool_calls)} tool(s):")
        messages.append(response)

        for call in response.tool_calls:
            fn     = tools_map.get(call["name"])
            result = fn.invoke(call["args"]) if fn else "Tool not found."
            # summarise result so log is readable
            snippet = str(result)[:200] if isinstance(result, str) else str(result)[:200]
            print(f"    → {call['name']}({list(call['args'].values())[0]!r:.60})")
            print(f"    ← {snippet}...")
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

        response = llm_with_tools.invoke(messages)

    print(f"\n  Rounds used: {rounds}")
    return response.content


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 11 — Web Search with Tavily  (manual tool loop)")
    print("Watch: Gemini picks tool → search runs → result read → answer\n")

    answer = research("Research Infosys SDE-1 interview process — rounds, topics, difficulty, salary.")
    print(f"\n{'='*60}\nFinal Answer:\n{answer}")
