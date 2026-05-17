"""Day 9 — LangChain Tools + Tavily Web Search
@tool registers a function the LLM can call. Docstring = when to use it."""

import os, time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_tavily import TavilySearch

load_dotenv()

def extract_text(content) -> str:
    if isinstance(content, str): return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

# ── model ──────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=800,
)

# ── shared tavily client ────────────────────────────────────────
_tavily = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"), max_results=4)


# ── tools ──────────────────────────────────────────────────────
# define what the LLM can search — docstring tells it WHEN to call each tool

@tool
def search_interview_process(company: str) -> str:
    """Search the web for the current interview process at a company.
    Returns real information about rounds, tests, and selection stages."""
    results = _tavily.invoke({"query": f"{company} interview process rounds fresher 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_salary_info(company: str, role: str) -> str:
    """Search the web for fresher salary and CTC at a company for a specific role.
    Returns salary ranges in LPA."""
    results = _tavily.invoke({"query": f"{company} {role} fresher salary CTC LPA 2024 India"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_preparation_tips(company: str, role: str) -> str:
    """Search for preparation tips and interview experiences for a company and role."""
    results = _tavily.invoke({"query": f"{company} {role} interview preparation tips experience 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_company_culture(company: str) -> str:
    """Search for work culture, work-life balance and employee reviews at a company."""
    results = _tavily.invoke({"query": f"{company} work culture employee review growth 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

ALL_TOOLS = [search_interview_process, search_salary_info,
             search_preparation_tips, search_company_culture]
TOOLS_MAP  = {t.name: t for t in ALL_TOOLS}


# ── phase 2: single question — LLM picks tools on its own ──────
def phase2_single_question(company: str, role: str):
    divider("PHASE 2 — LLM decides which tools to call")

    llm_with_tools = llm.bind_tools(ALL_TOOLS)     # attach tool list to model
    system = SystemMessage(content=(
        "You are a placement research assistant for Indian engineering students. "
        "Use tools to find real, current information. Always search before answering."
    ))

    question = f"I am applying for {role} at {company}. What is the interview process and how should I prepare?"
    print(f"Q: {question}\n")

    messages = [system, HumanMessage(content=question)]
    response = llm_with_tools.invoke(messages)

    rounds = 0
    while response.tool_calls and rounds < 5:       # loop until LLM stops calling tools
        rounds += 1
        messages.append(response)
        print(f"Round {rounds} — {len(response.tool_calls)} tool call(s):")

        for call in response.tool_calls:
            print(f"  → {call['name']}({call['args']})")
            tool_fn = TOOLS_MAP.get(call["name"])
            result  = tool_fn.invoke(call["args"]) if tool_fn else "Tool not found."
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

        time.sleep(3)
        response = llm_with_tools.invoke(messages)  # call again with search results added

    print(f"\nFinal answer after {rounds} round(s):\n")
    print(extract_text(response.content))


# ── phase 3: one turn of the interactive agent ─────────────────
def run_agent(user_input: str, history: list) -> tuple[str, list]:
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system = SystemMessage(content=(
        "You are a placement research agent for engineering students in India. "
        "Use tools for every factual question. Be concise and practical."
    ))

    history.append(HumanMessage(content=user_input))
    messages = [system] + history                   # system always first

    response = llm_with_tools.invoke(messages)

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
    divider("PHASE 3 — Interactive Agent  (quit to exit)")
    history = []                                    # in-session memory only

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("\nSession ended.")
            break

        print()
        try:
            answer, history = run_agent(user_input, history)
            print(f"\nAgent: {answer}\n")
        except Exception as e:
            print(f"[Error: {e}]\n")
            time.sleep(10)


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)

    company = input("Company: ").strip()
    role    = input("Role   : ").strip()
    if not company or not role:
        print("Both fields required.")
        exit(1)

    divider("PHASE 1 — Registered Tools")
    print("  search_interview_process  — rounds and stages")
    print("  search_salary_info        — CTC and compensation")
    print("  search_preparation_tips   — topics to study")
    print("  search_company_culture    — work culture and reviews")
    input("\nPress Enter to run Phase 2...")

    phase2_single_question(company, role)
    print("\nMoving to Phase 3 in 5 seconds...")
    time.sleep(5)

    phase3_interactive_agent()
