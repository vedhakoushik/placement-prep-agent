"""
Day 9 - LangChain Tools + Tavily Web Search
============================================
Day 8: prompt | model | parser  -> static knowledge inside the model
Day 9: model + tools            -> model can REACH OUT and fetch live data

Three things you'll learn:
  1. What a Tool is and how to make one with @tool
  2. How to bind tools to an LLM so it can decide when to use them
  3. Using Tavily (real-time web search) as a tool for company research
"""

import os, time, json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_tavily import TavilySearch

load_dotenv()

# ── Model setup ───────────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",          # 1500 req/day free vs 20/day for 2.5-flash
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=600,
)


# ============================================================================
# PART 1 — Custom Tool with @tool decorator
# A tool is just a Python function the LLM can choose to call.
# The docstring IS the tool's description — write it clearly!
# ============================================================================

@tool
def get_interview_rounds(company: str) -> str:
    """Returns the number of interview rounds and their names for a given Indian tech company."""
    data = {
        "wipro":   "3 rounds: Online Test → Technical Interview → HR",
        "tcs":     "3 rounds: TCS NQT (Online Test) → Technical → HR",
        "infosys": "3 rounds: InfyTQ Test → Technical Interview → HR",
        "accenture":"3 rounds: Cognitive Test → Technical → HR",
        "cognizant":"3 rounds: GAME (Online Test) → Technical → HR",
        "hcl":     "2 rounds: Technical Interview → HR",
    }
    return data.get(company.lower(), f"No data available for {company}. Try a major IT company.")


@tool
def get_salary_range(company: str, role: str) -> str:
    """Returns the approximate fresher salary range (CTC in LPA) for a role at an Indian tech company."""
    salary_map = {
        ("wipro",     "sde"):      "3.5 – 6.5 LPA",
        ("tcs",       "sde"):      "3.36 – 7 LPA",
        ("infosys",   "sde"):      "3.6 – 8 LPA",
        ("accenture", "analyst"):  "4.5 – 8 LPA",
        ("google",    "sde"):      "20 – 45 LPA",
        ("microsoft", "sde"):      "20 – 40 LPA",
    }
    key = (company.lower(), role.lower())
    return salary_map.get(key, f"Salary data not available for {role} at {company}.")


def demo_custom_tools():
    print("\n" + "="*60)
    print("PART 1 — Custom Tools (no internet, local lookup)")
    print("="*60)

    # Bind tools to the LLM — now it KNOWS these tools exist
    llm_with_tools = llm.bind_tools([get_interview_rounds, get_salary_range])

    question = "How many rounds does Wipro have, and what is the SDE salary?"
    print(f"\nQuestion: {question}")

    messages = [HumanMessage(content=question)]
    response = llm_with_tools.invoke(messages)

    # Check if the LLM decided to call a tool
    if response.tool_calls:
        print(f"\n→ LLM chose to call {len(response.tool_calls)} tool(s):")
        messages.append(response)

        for call in response.tool_calls:
            print(f"  • Tool: {call['name']}  Args: {call['args']}")

            # Actually run the tool
            if call["name"] == "get_interview_rounds":
                result = get_interview_rounds.invoke(call["args"])
            else:
                result = get_salary_range.invoke(call["args"])

            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
            print(f"  • Result: {result}")

        # Feed tool results back -> get final answer
        final   = llm_with_tools.invoke(messages)
        content = final.content
        # Gemini sometimes returns content as a list of blocks — extract text
        if isinstance(content, list):
            content = " ".join(b.get("text","") for b in content if isinstance(b, dict))
        print(f"\n✓ Final Answer:\n{content}")
    else:
        content = response.content
        if isinstance(content, list):
            content = " ".join(b.get("text","") for b in content if isinstance(b, dict))
        print(f"\n✓ Answer (no tool used):\n{content}")


# ============================================================================
# PART 2 — Tavily Web Search Tool
# Tavily is a search engine built for AI agents.
# Unlike Google, it returns clean text (not HTML) that fits in a prompt.
# ============================================================================

def demo_tavily_search(company: str):
    print("\n" + "="*60)
    print("PART 2 — Tavily Web Search (live internet data)")
    print("="*60)

    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("⚠  TAVILY_API_KEY not set in .env — skipping live search demo.")
        print("   Get a free key at: https://app.tavily.com")
        return

    # Tavily search tool — max_results=3 keeps token usage low
    search = TavilySearch(
        tavily_api_key=tavily_key,
        max_results=3,
    )

    query = f"{company} interview process fresher 2024 India"
    print(f"\nSearching: '{query}'")

    raw     = search.invoke({"query": query})
    results = raw if isinstance(raw, list) else raw.get("results", [])

    print(f"\n-> Got {len(results)} results from the web:")
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] {r.get('url', 'N/A')}")
        print(f"      {r.get('content','')[:200]}...")

    # Now feed those results to the LLM to synthesise an answer
    context = "\n\n".join(
        f"Source {i+1}: {r['content']}" for i, r in enumerate(results)
    )
    prompt = f"""Based on the following web search results, summarise the interview process
at {company} for a fresher software engineer. Be concise and practical.

Search results:
{context}

Summary:"""

    print(f"\n→ Feeding results to LLM for synthesis...")
    answer = llm.invoke(prompt)
    print(f"\n✓ Synthesised Answer:\n{answer.content}")


# ============================================================================
# PART 3 — LLM decides WHICH tool to use (tool routing)
# Give the LLM both tools. Ask a question. Watch it pick the right one.
# ============================================================================

def demo_tool_routing():
    print("\n" + "="*60)
    print("PART 3 — Tool Routing (LLM decides which tool to call)")
    print("="*60)

    llm_with_tools = llm.bind_tools([get_interview_rounds, get_salary_range])

    questions = [
        "What rounds does TCS have for campus placements?",
        "What is the fresher salary for SDE at Google?",
    ]

    tools_map = {
        "get_interview_rounds": get_interview_rounds,
        "get_salary_range":     get_salary_range,
    }

    for question in questions:
        print(f"\nQ: {question}")
        response = llm_with_tools.invoke([HumanMessage(content=question)])

        if response.tool_calls:
            call = response.tool_calls[0]
            print(f"→ Tool selected: {call['name']}")
            result = tools_map[call["name"]].invoke(call["args"])
            print(f"→ Tool result:   {result}")

            # Final answer
            messages = [
                HumanMessage(content=question),
                response,
                ToolMessage(content=result, tool_call_id=call["id"]),
            ]
            final   = llm_with_tools.invoke(messages)
            content = final.content
            if isinstance(content, list):
                content = " ".join(b.get("text","") for b in content if isinstance(b, dict))
            print(f"✓ Answer: {content}")
        else:
            c = response.content
            if isinstance(c, list):
                c = " ".join(b.get("text","") for b in c if isinstance(b, dict))
            print(f"✓ Answer (no tool): {c}")

        time.sleep(5)


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Day 9 - LangChain Tools + Tavily Web Search")
    print("Tools let the LLM reach OUTSIDE its training data\n")

    company = input("Enter a company name for the Tavily search demo: ").strip() or "Wipro"

    # Part 1: Custom tools
    demo_custom_tools()

    time.sleep(6)

    # Part 2: Live web search (needs TAVILY_API_KEY)
    demo_tavily_search(company)

    time.sleep(6)

    # Part 3: LLM picks the right tool on its own
    demo_tool_routing()

    print("\n" + "="*60)
    print("Day 9 complete!")
    print("Day 8: prompt | model | parser  (static - no live data)")
    print("Day 9: model + tools            (dynamic, live data)")
    print("Day 10: chains + tools + memory (full research agent)")
    print("="*60)
