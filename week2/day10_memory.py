"""Day 10 — Persistent Memory: Agent That Remembers Across Sessions
save_memory → JSON file. load_memory → back to LangChain objects. trim_memory → cap size."""

import os, json, time
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_tavily import TavilySearch

load_dotenv()

MEMORY_FILE = Path(__file__).parent / "agent_memory.json"
MAX_TURNS   = 10    # drop oldest turns beyond this to avoid context overflow

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

# ── tavily ─────────────────────────────────────────────────────
_tavily = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"), max_results=4)


# ── tools (same 4 as day 9) ────────────────────────────────────
@tool
def search_interview_process(company: str) -> str:
    """Search the web for the current interview process at a company."""
    results = _tavily.invoke({"query": f"{company} interview process rounds fresher 2024"})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:3])
    return str(results)

@tool
def search_salary_info(company: str, role: str) -> str:
    """Search the web for fresher salary and CTC for a role at a company."""
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


# ── memory layer ───────────────────────────────────────────────

def save_memory(history: list):
    """Convert LangChain messages → JSON and write to disk.
    Skips ToolMessages (raw search data) and blank AIMessages (tool-call-only responses)."""
    records = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            records.append({"role": "human", "content": extract_text(msg.content)})
        elif isinstance(msg, AIMessage):
            text = extract_text(msg.content)
            if text.strip():                        # skip AIMessages with no text
                records.append({"role": "ai", "content": text})
    MEMORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def load_memory() -> list:
    """Read JSON from disk → rebuild HumanMessage / AIMessage objects."""
    if not MEMORY_FILE.exists():
        return []                                   # first run — no file yet
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
        print(f"[Warning: could not load memory — {e}]")
        return []


def trim_memory(history: list, max_turns: int = MAX_TURNS) -> list:
    """Keep only the last max_turns human messages worth of history.
    Finds each HumanMessage position, slices from the (n - max_turns)th one."""
    human_indices = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(human_indices) <= max_turns:
        return history
    keep_from = human_indices[-max_turns]           # index of the oldest turn to keep
    return history[keep_from:]


# ── phase 1: concept overview (no api calls) ───────────────────
def phase1_explain():
    divider("PHASE 1 — Memory Concepts")
    print("  Day 9: history list lives in RAM — gone when you quit.")
    print("  Day 10: history saved to JSON — loaded back next session.")
    print()
    print("  save_memory()  →  history list  →  agent_memory.json")
    print("  load_memory()  →  agent_memory.json  →  history list")
    print("  trim_memory()  →  drop oldest turns beyond MAX_TURNS")
    print()
    print("  Only HumanMessage + AIMessage are saved.")
    print("  ToolMessage (raw search text) is skipped — transient data.")


# ── phase 2: file memory demo (no api calls) ───────────────────
def phase2_file_demo():
    divider("PHASE 2 — Save / Load Demo  (no API calls)")

    # create a fake conversation to test save → load cycle
    fake = [
        HumanMessage(content="What is the interview process at Infosys?"),
        AIMessage(content="Infosys has 3 rounds: InfyTQ online test, technical interview, HR."),
        HumanMessage(content="What is the typical salary?"),
        AIMessage(content="Infosys freshers typically get 3.6 LPA base CTC."),
    ]

    print(f"Saving {len(fake)} messages...")
    save_memory(fake)
    print(f"  Written → {MEMORY_FILE}\n")

    print("Loading back...")
    loaded = load_memory()
    print(f"  Loaded {len(loaded)} messages\n")

    for msg in loaded:
        label = "You  " if isinstance(msg, HumanMessage) else "Agent"
        print(f"  [{label}]: {extract_text(msg.content)[:75]}")

    print(f"\n  Turns in memory : {sum(1 for m in loaded if isinstance(m, HumanMessage))}")
    print(f"  MAX_TURNS limit : {MAX_TURNS}  → no trim needed yet")


# ── phase 3: one turn of the persistent agent ──────────────────
def run_agent(user_input: str, history: list) -> tuple[str, list]:
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system = SystemMessage(content=(
        "You are a placement research agent for engineering students in India. "
        "Use tools for factual questions. Use past history for context. Be concise."
    ))

    history.append(HumanMessage(content=user_input))
    messages = [system] + history                   # system first, then full history

    response = llm_with_tools.invoke(messages)

    rounds = 0
    while response.tool_calls and rounds < 4:       # tool loop
        rounds += 1
        messages.append(response)
        history.append(response)

        for call in response.tool_calls:
            print(f"  [searching: {call['name']}({call['args']})]")
            tool_fn = TOOLS_MAP.get(call["name"])
            result  = tool_fn.invoke(call["args"]) if tool_fn else "Tool not found."
            tm = ToolMessage(content=result, tool_call_id=call["id"])  # id links result to call
            messages.append(tm)
            history.append(tm)

        time.sleep(3)
        response = llm_with_tools.invoke(messages)

    answer = extract_text(response.content)
    history.append(response)
    return answer, history


def phase3_persistent_agent():
    divider("PHASE 3 — Persistent Agent  (memory / clear / quit)")

    history    = load_memory()                      # load previous session
    past_turns = sum(1 for m in history if isinstance(m, HumanMessage))

    if past_turns > 0:
        print(f"  Loaded {past_turns} past turn(s) from {MEMORY_FILE.name}")
        print("  Try: 'what did I ask before?' to test memory.\n")
    else:
        print("  No previous memory — starting fresh.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        # built-in commands
        if user_input.lower() in ("quit", "exit", "q"):
            trimmed = trim_memory(history)
            save_memory(trimmed)
            n = sum(1 for m in trimmed if isinstance(m, HumanMessage))
            print(f"\nSaved {n} turn(s) to {MEMORY_FILE.name}")
            break

        if user_input.lower() == "clear":
            history = []
            if MEMORY_FILE.exists(): MEMORY_FILE.unlink()
            print("[Memory wiped]\n")
            continue

        if user_input.lower() == "memory":
            pairs = [(m, history[i+1]) for i, m in enumerate(history)
                     if isinstance(m, HumanMessage) and i+1 < len(history)
                     and isinstance(history[i+1], AIMessage)]
            if not pairs:
                print("[No history yet]\n")
            else:
                print(f"\n[Last 5 of {len(pairs)} turn(s)]\n")
                for j, (q, a) in enumerate(pairs[-5:], 1):
                    print(f"  Q: {extract_text(q.content)[:70]}")
                    print(f"  A: {extract_text(a.content)[:70]}\n")
            continue

        # agent turn
        print()
        try:
            answer, history = run_agent(user_input, history)
            print(f"\nAgent: {answer}\n")
            save_memory(trim_memory(history))       # auto-save after every turn
        except Exception as e:
            print(f"[Error: {e}]\n")
            time.sleep(10)


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)

    phase1_explain()
    phase2_file_demo()
    phase3_persistent_agent()
