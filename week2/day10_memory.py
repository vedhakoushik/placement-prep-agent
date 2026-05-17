"""
Day 10 - Memory: Agent That Remembers Across Sessions
======================================================
Day 9: The agent forgot everything the moment you quit.
Day 10: The agent saves its memory to a JSON file and picks
        up exactly where it left off next time you run it.

Three phases:
  1. What is Memory?  - the history list explained visually
  2. File Memory      - serialize / deserialize messages to JSON
  3. Persistent Agent - Day 9 tools + Day 10 memory, survives across runs
"""

import os, json, time
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_tavily import TavilySearch

load_dotenv()

MEMORY_FILE = Path(__file__).parent / "agent_memory.json"
MAX_TURNS   = 10   # keep last 10 human turns in memory (prevents context overflow)


# ── helpers ───────────────────────────────────────────────────────────────────
def extract_text(content) -> str:
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

# ── Tavily ────────────────────────────────────────────────────────────────────
_tavily = TavilySearch(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=4,
)


# ── Tools (same 4 as Day 9, trimmed docstrings) ───────────────────────────────
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
    """Search the web for fresher salary and CTC for a specific role at a company.
    Returns salary ranges in LPA (Lakhs Per Annum)."""
    results = _tavily.invoke({"query": f"{company} {role} fresher salary CTC LPA 2024 India"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_preparation_tips(company: str, role: str) -> str:
    """Search for preparation tips, study topics, and interview experiences
    for a specific company and role."""
    results = _tavily.invoke({"query": f"{company} {role} interview preparation tips experience 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_company_culture(company: str) -> str:
    """Search for work culture, work-life balance, growth opportunities,
    and employee reviews at a company."""
    results = _tavily.invoke({"query": f"{company} work culture employee review growth 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

ALL_TOOLS = [search_interview_process, search_salary_info,
             search_preparation_tips, search_company_culture]
TOOLS_MAP = {t.name: t for t in ALL_TOOLS}


# =============================================================================
# MEMORY LAYER
# Three functions that are the entire "memory system":
#   save_memory  -> history list  -> JSON file
#   load_memory  -> JSON file     -> history list
#   trim_memory  -> drop oldest turns so context never overflows
# =============================================================================

def save_memory(history: list):
    """Serialize LangChain messages to JSON and write to disk.
    Only saves HumanMessage and text AIMessage objects.
    ToolMessages are transient search results — we skip them.
    """
    records = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            records.append({"role": "human", "content": extract_text(msg.content)})
        elif isinstance(msg, AIMessage):
            text = extract_text(msg.content)
            if text.strip():   # skip pure tool-call responses with no text
                records.append({"role": "ai", "content": text})
    MEMORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def load_memory() -> list:
    """Read JSON from disk and rebuild LangChain message objects."""
    if not MEMORY_FILE.exists():
        return []
    try:
        records = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        messages = []
        for r in records:
            if r["role"] == "human":
                messages.append(HumanMessage(content=r["content"]))
            elif r["role"] == "ai":
                messages.append(AIMessage(content=r["content"]))
        return messages
    except Exception as e:
        print(f"[Warning: could not load memory: {e}]")
        return []


def trim_memory(history: list, max_turns: int = MAX_TURNS) -> list:
    """Keep only the last max_turns human messages worth of history.
    Prevents the context window from growing without bound across many sessions.
    """
    human_indices = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(human_indices) <= max_turns:
        return history
    # Slice from the (len - max_turns)th human message onwards
    keep_from = human_indices[-max_turns]
    return history[keep_from:]


# =============================================================================
# PHASE 1 - What is Memory?
# =============================================================================

def phase1_explain():
    divider("PHASE 1 - What is Memory?")
    print("""
Memory = the list of past messages the LLM receives on every call.

WITHOUT memory (stateless):
  Turn 1  You:   "Tell me about TCS interviews."
          Agent: "TCS has 3 rounds: online test, technical, HR."
  Turn 2  You:   "What is the salary?"
          Agent: "Salary of what? I have no context."  <- WRONG

WITH in-session memory (Day 9):
  The history list grows each turn. Every call includes all prior messages,
  so the LLM always has context. But the list lives only in RAM.
  When you quit -> everything is gone.

WITH persistent memory (Day 10):
  The history list is saved to agent_memory.json after every turn.
  Next session -> file is loaded -> agent remembers everything.

  Session 1  You: "Which company did we research?"
             Agent: "We haven't researched anything yet."
  << quit, come back tomorrow >>
  Session 2  You: "Which company did we research?"
             Agent: "Yesterday you asked about TCS interviews and salary."

Memory storage format (agent_memory.json):
  [
    {"role": "human", "content": "Tell me about TCS interviews"},
    {"role": "ai",    "content": "TCS has 3 rounds..."},
    {"role": "human", "content": "What about the salary?"},
    {"role": "ai",    "content": "TCS freshers get 3.5-7 LPA..."}
  ]

Tools registered:
  - search_interview_process  (company)
  - search_salary_info        (company, role)
  - search_preparation_tips   (company, role)
  - search_company_culture    (company)
""")


# =============================================================================
# PHASE 2 - File Memory Demo (no API calls needed)
# =============================================================================

def phase2_file_demo():
    divider("PHASE 2 - File Memory Demo (no API calls)")
    print("Saving a sample conversation and reloading it from disk.\n")

    # Build a fake conversation
    fake = [
        HumanMessage(content="What is the interview process at Infosys?"),
        AIMessage(content="Infosys has 3 rounds: InfyTQ online test, technical interview, HR round."),
        HumanMessage(content="What is the typical salary?"),
        AIMessage(content="Infosys freshers typically receive 3.6 LPA as base CTC (up to 6.5 LPA for specialist roles)."),
    ]

    print(f"Saving {len(fake)} messages...")
    save_memory(fake)
    print(f"  Written to: {MEMORY_FILE}\n")

    print("Loading back from disk...")
    loaded = load_memory()
    print(f"  Loaded {len(loaded)} messages\n")

    for msg in loaded:
        label = "You  " if isinstance(msg, HumanMessage) else "Agent"
        print(f"  [{label}]: {extract_text(msg.content)[:80]}")

    # Demo trim
    print(f"\nTrim demo (MAX_TURNS = {MAX_TURNS}):")
    print(f"  Current turns: {sum(1 for m in loaded if isinstance(m, HumanMessage))}")
    trimmed = trim_memory(loaded)
    print(f"  After trim   : {sum(1 for m in trimmed if isinstance(m, HumanMessage))} (no change — under limit)")

    print("\nFile memory works correctly. Phase 3 attaches this to a live agent.")


# =============================================================================
# PHASE 3 - Persistent Agent
# =============================================================================

def run_agent(user_input: str, history: list) -> tuple[str, list]:
    """One turn of the agent. Returns (answer, updated_history)."""
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system = SystemMessage(content=(
        "You are a placement research agent helping an engineering student in India. "
        "Use tools to find real, current information — never make up facts. "
        "You have access to past conversation history — use it to give contextual answers. "
        "Be concise and practical."
    ))

    history.append(HumanMessage(content=user_input))
    messages = [system] + history

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


def phase3_persistent_agent():
    divider("PHASE 3 - Persistent Agent (type 'quit' to save and exit)")

    history = load_memory()
    past_turns = sum(1 for m in history if isinstance(m, HumanMessage))

    if past_turns > 0:
        print(f"Memory loaded: {past_turns} past turn(s) found.")
        print(f"File: {MEMORY_FILE}")
        print("Try: 'what companies did I ask about?' or 'what did I research last time?'\n")
    else:
        print("No previous memory found — starting fresh.")
        print("Ask anything about any company, role, salary, prep, or culture.\n")

    print("Commands: 'memory' = show history | 'clear' = wipe memory | 'quit' = save & exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        # ── built-in commands ──────────────────────────────────────────────────
        if user_input.lower() in ("quit", "exit", "q"):
            print("\nSaving memory...")
            trimmed = trim_memory(history)
            save_memory(trimmed)
            n = sum(1 for m in trimmed if isinstance(m, HumanMessage))
            print(f"Saved {n} turn(s) to {MEMORY_FILE.name}")
            break

        if user_input.lower() == "clear":
            history = []
            if MEMORY_FILE.exists():
                MEMORY_FILE.unlink()
            print("[Memory wiped. Starting fresh.]\n")
            continue

        if user_input.lower() == "memory":
            turns = [(m, history[i + 1])
                     for i, m in enumerate(history)
                     if isinstance(m, HumanMessage)
                     and i + 1 < len(history)
                     and isinstance(history[i + 1], AIMessage)]
            if not turns:
                print("[No conversation history yet.]\n")
            else:
                print(f"\n[Showing last 5 of {len(turns)} turn(s)]\n")
                for j, (q, a) in enumerate(turns[-5:], 1):
                    print(f"  Q: {extract_text(q.content)[:70]}")
                    print(f"  A: {extract_text(a.content)[:70]}\n")
            continue

        # ── agent turn ─────────────────────────────────────────────────────────
        print("\n[Agent is researching...]\n")
        try:
            answer, history = run_agent(user_input, history)
            print(f"Agent: {answer}\n")
            # Auto-save after every turn (protects against Ctrl+C mid-session)
            save_memory(trim_memory(history))
        except Exception as e:
            print(f"[Error: {e}]\n")
            time.sleep(10)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Day 10 - Memory: Agent That Remembers Across Sessions")
    print("Same tools as Day 9, now with a persistent JSON memory layer.\n")

    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)

    phase1_explain()
    input("Press Enter to run Phase 2 (file memory demo — no API calls)...")

    phase2_file_demo()
    input("\nPress Enter to start Phase 3 (live persistent agent)...")

    phase3_persistent_agent()

    divider("Day 10 Complete")
    print("Day  9: model + tools + agent loop                    (live search)")
    print("Day 10: model + tools + agent loop + persistent memory (remembers)")
    print("Day 11: structured output — JSON schemas, Pydantic models, validation")
    print("=" * 60)
