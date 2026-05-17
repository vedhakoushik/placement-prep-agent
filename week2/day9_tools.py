"""
Day 9 - LangChain Tools + Tavily Web Search
============================================
Core idea: Tools give the LLM the ability to ACT, not just recall.
           Instead of knowing things, it reaches out and FINDS them.

This script works for ANY company, ANY role, ANY question.
No hardcoded data. Everything is live.

Three phases:
  1. What a Tool is  - build a real dynamic tool with @tool
  2. Tool + LLM      - let the LLM decide what to search and when
  3. Full agent loop - user asks anything, agent researches and answers
"""

import os, time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_tavily import TavilySearch

load_dotenv()

# ── helpers ───────────────────────────────────────────────────────────────────
def extract_text(content) -> str:
    """Gemini sometimes returns content as a list of blocks. Pull out the text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def divider(title=""):
    line = "=" * 60
    print(f"\n{line}")
    if title:
        print(title)
        print(line)


# ── Model ─────────────────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=800,
)

# ── Tavily client (shared across tools) ───────────────────────────────────────
_tavily = TavilySearch(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=4,
)


# =============================================================================
# PHASE 1 - What is a Tool?
# A Tool is a Python function the LLM can call whenever it needs to.
# The @tool decorator registers it and uses the docstring as the description.
# The LLM reads the description to decide WHEN and HOW to call it.
# =============================================================================

@tool
def search_interview_process(company: str) -> str:
    """
    Search the web for the current interview process at a company.
    Returns real information about rounds, tests, and selection stages.
    Use this when the user asks about how to get into a company.
    """
    query = f"{company} interview process selection rounds fresher 2024"
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)


@tool
def search_salary_info(company: str, role: str) -> str:
    """
    Search the web for fresher salary and CTC information at a company for a specific role.
    Returns real, up-to-date salary ranges in LPA (Lakhs Per Annum).
    Use this when the user asks about pay, CTC, or compensation.
    """
    query = f"{company} {role} fresher salary CTC LPA package 2024 India"
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)


@tool
def search_preparation_tips(company: str, role: str) -> str:
    """
    Search the web for preparation tips, topics to study, and interview experiences
    for a specific company and role. Returns real advice from candidates who got placed.
    Use this when the user asks how to prepare or what to study.
    """
    query = f"{company} {role} interview preparation tips topics syllabus experience 2024"
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)


@tool
def search_company_culture(company: str) -> str:
    """
    Search for information about work culture, work-life balance, growth opportunities,
    and employee reviews at a company. Use this when the user asks about life at the company.
    """
    query = f"{company} work culture employee review work life balance growth 2024"
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)


ALL_TOOLS = [
    search_interview_process,
    search_salary_info,
    search_preparation_tips,
    search_company_culture,
]

TOOLS_MAP = {t.name: t for t in ALL_TOOLS}


# =============================================================================
# PHASE 2 - LLM + Tools: one question, LLM picks its own tools
# =============================================================================

def phase2_single_question(company: str, role: str):
    divider("PHASE 2 - LLM picks which tools to call (you ask, it decides)")

    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system = SystemMessage(content=(
        "You are a placement research assistant for Indian engineering students. "
        "Use the available tools to find real, current information. "
        "Always search before answering - never rely on assumptions."
    ))

    question = f"I am applying for {role} at {company}. What is the interview process and how should I prepare?"
    print(f"\nQuestion: {question}")
    print("\n[LLM is deciding which tools to call...]\n")

    messages = [system, HumanMessage(content=question)]
    response = llm_with_tools.invoke(messages)

    # Agent loop: keep calling tools until the LLM stops asking for them
    rounds = 0
    while response.tool_calls and rounds < 5:
        rounds += 1
        messages.append(response)
        print(f"Round {rounds} - LLM called {len(response.tool_calls)} tool(s):")

        for call in response.tool_calls:
            print(f"  -> {call['name']}({call['args']})")
            tool_fn  = TOOLS_MAP.get(call["name"])
            result   = tool_fn.invoke(call["args"]) if tool_fn else "Tool not found."
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
            print(f"     [got {len(result)} chars of search results]")

        time.sleep(3)
        response = llm_with_tools.invoke(messages)

    print(f"\nFinal Answer after {rounds} tool round(s):\n")
    print(extract_text(response.content))


# =============================================================================
# PHASE 3 - Full dynamic agent: user drives the conversation
# The agent keeps researching until the user is done.
# No script, no fixed questions - completely open-ended.
# =============================================================================

def run_agent(user_input: str, history: list) -> tuple[str, list]:
    """Run one turn of the agent. Returns (answer, updated_history)."""
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system = SystemMessage(content=(
        "You are a placement research agent helping an engineering student in India. "
        "For every question, use tools to find real, current information from the web. "
        "Never make up numbers or facts — always search first. "
        "Be concise, practical, and specific to the student's situation."
    ))

    history.append(HumanMessage(content=user_input))
    messages = [system] + history

    response = llm_with_tools.invoke(messages)

    # Tool loop
    rounds = 0
    while response.tool_calls and rounds < 4:
        rounds += 1
        messages.append(response)
        history.append(response)

        for call in response.tool_calls:
            print(f"  [searching: {call['name']}({call['args']})]")
            tool_fn = TOOLS_MAP.get(call["name"])
            result  = tool_fn.invoke(call["args"]) if tool_fn else "Tool not found."
            tm = ToolMessage(content=result, tool_call_id=call["id"])
            messages.append(tm)
            history.append(tm)

        time.sleep(3)
        response = llm_with_tools.invoke(messages)

    answer = extract_text(response.content)
    history.append(response)
    return answer, history


def phase3_interactive_agent():
    divider("PHASE 3 - Interactive Research Agent (type 'quit' to exit)")
    print("Ask anything about any company, role, salary, prep, culture.")
    print("The agent searches the web and answers in real time.\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("\nAgent session ended.")
            break

        print("\n[Agent is researching...]\n")
        try:
            answer, history = run_agent(user_input, history)
            print(f"Agent: {answer}\n")
        except Exception as e:
            print(f"[Error: {e}]\n")
            time.sleep(10)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Day 9 - LangChain Tools + Tavily Web Search")
    print("Dynamic agent: works for any company, any role, any question.\n")

    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        print("Get a free key at https://app.tavily.com and add it to .env")
        exit(1)

    company = input("Company you are targeting: ").strip()
    role    = input("Role you are applying for : ").strip()

    if not company or not role:
        print("Please enter both company and role.")
        exit(1)

    # Phase 1: explain tools (no API call needed)
    divider("PHASE 1 - What is a Tool?")
    print("""
A Tool is a Python function the LLM can CALL during its reasoning.
You define it with @tool. The docstring tells the LLM when to use it.

Tools registered for this agent:
  - search_interview_process  -> searches interview rounds and selection stages
  - search_salary_info        -> searches CTC and compensation data
  - search_preparation_tips   -> searches what to study and how to prepare
  - search_company_culture    -> searches work culture and employee reviews

The LLM sees these descriptions and decides on its own which to call.
No if-else routing. No hardcoded lookup tables.
""")

    input("Press Enter to run Phase 2...")

    # Phase 2: one question, LLM picks tools
    phase2_single_question(company, role)

    print("\n\nPhase 2 done. Moving to Phase 3 in 5 seconds...")
    time.sleep(5)

    # Phase 3: fully interactive agent
    phase3_interactive_agent()

    divider("Day 9 Complete")
    print("Day 8: prompt | model | parser    (static, one-shot)")
    print("Day 9: model + tools + agent loop (dynamic, live web search)")
    print("Day 10: add memory so the agent remembers across sessions")
    print("=" * 60)
