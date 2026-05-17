"""Day 14 — Week 2 Capstone: Full Company Research Chain
Days 8-13 combined: LCEL chains + tools + memory + structured output + robustness.
Input: company + role  →  Output: markdown report saved to week2/reports/."""

import os, json, time
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnableLambda
from langchain_tavily import TavilySearch

load_dotenv()

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
MEMORY_FILE = Path(__file__).parent / "agent_memory.json"
MAX_TURNS   = 10

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=1000,
)
_tavily = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"), max_results=4)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

def extract_text(content) -> str:
    if isinstance(content, str): return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)

def web_search(query: str, n: int = 3) -> str:
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:n])
    return str(results)


# ── schemas (day 11) ───────────────────────────────────────────
class CompanySnapshot(BaseModel):
    name:             str       = Field(description="Company name")
    founded:          str       = Field(description="Year founded")
    headquarters:     str       = Field(description="City and country")
    tech_stack:       list[str] = Field(description="Main technologies")
    interview_rounds: list[str] = Field(description="Interview stages in order")
    difficulty:       str       = Field(description="easy / medium / hard")
    fresher_ctc:      str       = Field(description="Fresher CTC range in LPA")
    culture_rating:   str       = Field(description="excellent / good / average / poor")

class PrepPlan(BaseModel):
    priority_topics:     list[str] = Field(description="Top 5 topics to study")
    skills_to_highlight: list[str] = Field(description="Skills to emphasise")
    timeline_weeks:      int       = Field(description="Weeks of prep needed")
    daily_routine:       str       = Field(description="Short daily study routine (2-3 sentences)")
    avoid:               list[str] = Field(description="3 common mistakes to avoid")


# ── memory layer (day 10) ──────────────────────────────────────
def load_memory() -> list:
    if not MEMORY_FILE.exists(): return []
    try:
        records = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        msgs = []
        for r in records:
            if r["role"] == "human": msgs.append(HumanMessage(content=r["content"]))
            elif r["role"] == "ai":  msgs.append(AIMessage(content=r["content"]))
        return msgs
    except: return []

def save_memory(history: list):
    records = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            records.append({"role": "human", "content": extract_text(msg.content)})
        elif isinstance(msg, AIMessage):
            text = extract_text(msg.content)
            if text.strip(): records.append({"role": "ai", "content": text})
    MEMORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

def trim_memory(history: list) -> list:
    idx = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(idx) <= MAX_TURNS: return history
    return history[idx[-MAX_TURNS]:]


# ── tools (day 9) ─────────────────────────────────────────────
@tool
def search_interview_process(company: str) -> str:
    """Search the web for the current interview process at a company."""
    return web_search(f"{company} interview process rounds fresher 2024")

@tool
def search_salary_info(company: str, role: str) -> str:
    """Search for fresher salary and CTC for a role at a company."""
    return web_search(f"{company} {role} fresher salary CTC LPA 2024 India")

@tool
def search_preparation_tips(company: str, role: str) -> str:
    """Search for preparation tips and interview experiences."""
    return web_search(f"{company} {role} interview preparation tips experience 2024")

@tool
def search_company_culture(company: str) -> str:
    """Search for work culture, work-life balance and employee reviews."""
    return web_search(f"{company} work culture employee review growth 2024")

ALL_TOOLS = [search_interview_process, search_salary_info,
             search_preparation_tips, search_company_culture]
TOOLS_MAP  = {t.name: t for t in ALL_TOOLS}


# ── stage 1: parallel web research (day 12) ────────────────────
def stage1_parallel_research(company: str, role: str) -> dict:
    print("  Stage 1: parallel search (4 queries at once)...")

    parallel = RunnableParallel({
        "interview": RunnableLambda(lambda x: web_search(f"{x['company']} interview process 2024")),
        "salary":    RunnableLambda(lambda x: web_search(f"{x['company']} {x['role']} salary LPA 2024")),
        "prep":      RunnableLambda(lambda x: web_search(f"{x['company']} {x['role']} preparation 2024")),
        "culture":   RunnableLambda(lambda x: web_search(f"{x['company']} work culture review 2024")),
    })

    raw = parallel.invoke({"company": company, "role": role})
    print(f"     Collected {sum(len(v) for v in raw.values()):,} chars")
    return raw


# ── stage 2: structured extraction (day 11) ────────────────────
def stage2_extract_structured(company: str, role: str, raw: dict):
    print("  Stage 2: structured extraction...")

    clip = lambda k: raw[k][:700]

    # extract CompanySnapshot
    snap_llm = llm.with_structured_output(CompanySnapshot)
    time.sleep(3)
    try:
        snapshot = snap_llm.invoke(
            f"Extract a company snapshot for {company}.\n\n"
            f"Interview:\n{clip('interview')}\nSalary:\n{clip('salary')}\nCulture:\n{clip('culture')}"
        )
    except Exception:                               # fallback if extraction fails
        snapshot = CompanySnapshot(
            name=company, founded="N/A", headquarters="India",
            tech_stack=["N/A"], interview_rounds=["Online Test", "Technical", "HR"],
            difficulty="medium", fresher_ctc="3-6 LPA", culture_rating="good",
        )

    # extract PrepPlan
    plan_llm = llm.with_structured_output(PrepPlan)
    time.sleep(3)
    try:
        prep_plan = plan_llm.invoke(
            f"Create a prep plan for {role} at {company}.\n\n"
            f"Tips:\n{clip('prep')}\nInterview:\n{clip('interview')}"
        )
    except Exception:                               # fallback if extraction fails
        prep_plan = PrepPlan(
            priority_topics=["DSA", "OOP", "DBMS", "OS", "CN"],
            skills_to_highlight=["Problem solving", "Communication"],
            timeline_weeks=4,
            daily_routine="Study DSA 2 hrs, review concepts 1 hr, solve 2 problems.",
            avoid=["Skipping mock interviews", "Ignoring HR prep", "Skipping aptitude"],
        )

    print(f"     Snapshot: difficulty={snapshot.difficulty}, ctc={snapshot.fresher_ctc}")
    print(f"     Plan    : {prep_plan.timeline_weeks} weeks, {len(prep_plan.priority_topics)} topics")
    return snapshot, prep_plan


# ── stage 3: narrative generation (day 8 lcel) ─────────────────
def stage3_narrative(company: str, role: str, raw: dict, snapshot: CompanySnapshot) -> dict:
    print("  Stage 3: generating narrative sections...")

    def run(prompt_text: str) -> str:
        return (ChatPromptTemplate.from_template("{text}") | llm | StrOutputParser()).invoke({"text": prompt_text})

    time.sleep(3)
    intro = run(
        f"Write a 3-sentence intro for a placement report on {role} at {company}. "
        f"Mention difficulty ({snapshot.difficulty}), CTC ({snapshot.fresher_ctc}), "
        f"and one fact from: {raw['culture'][:300]}"
    )
    time.sleep(3)
    tips = run(
        f"Based on this research, write 4 numbered prep tips for a fresher at {company}:\n"
        f"{raw['prep'][:600]}"
    )
    print("     Narrative ready")
    return {"intro": intro, "tips": tips}


# ── stage 4: build and save markdown report ─────────────────────
def stage4_save_report(company: str, role: str,
                        snapshot: CompanySnapshot, plan: PrepPlan, narrative: dict) -> Path:
    print("  Stage 4: writing markdown report...")

    report = f"""# Placement Research Report
## {role} at {snapshot.name}

---

### Overview
{narrative['intro']}

| Field | Detail |
|---|---|
| Founded | {snapshot.founded} |
| Headquarters | {snapshot.headquarters} |
| Difficulty | {snapshot.difficulty.title()} |
| Fresher CTC | {snapshot.fresher_ctc} |
| Culture | {snapshot.culture_rating.title()} |
| Prep Timeline | {plan.timeline_weeks} week(s) |

---

### Tech Stack
{', '.join(snapshot.tech_stack)}

---

### Interview Rounds
{chr(10).join(f"{i+1}. {r}" for i, r in enumerate(snapshot.interview_rounds))}

---

### Preparation Plan

**Priority Topics**
{chr(10).join(f"- {t}" for t in plan.priority_topics)}

**Skills to Highlight**
{', '.join(plan.skills_to_highlight)}

**Daily Routine**
{plan.daily_routine}

**Avoid**
{chr(10).join(f"- {a}" for a in plan.avoid)}

---

### Expert Tips
{narrative['tips']}

---
*Generated by Placement Prep Agent — Week 2 Capstone*
"""

    path = REPORTS_DIR / f"{company.lower().replace(' ','_')}_{role.lower().replace(' ','_')}.md"
    path.write_text(report, encoding="utf-8")
    print(f"     Saved → {path}")
    return path


# ── stage 5: follow-up chat with memory (day 10) ───────────────
def stage5_followup_chat(company: str, role: str, history: list):
    divider("STAGE 5 — Follow-up Chat  (done to finish)")
    print(f"Context: {role} at {company}. Ask anything to dig deeper.\n")

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system = SystemMessage(content=(
        f"You are a placement advisor. The user just researched {role} at {company}. "
        "Use tools for live data. Be concise."
    ))

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("done", "quit", "exit"):
            break

        history.append(HumanMessage(content=user_input))
        messages = [system] + history
        print()

        response = llm_with_tools.invoke(messages)

        rounds = 0
        while response.tool_calls and rounds < 3:
            rounds += 1
            messages.append(response)
            history.append(response)
            for call in response.tool_calls:
                print(f"  [searching: {call['name']}]")
                fn     = TOOLS_MAP.get(call["name"])
                result = fn.invoke(call["args"]) if fn else "Tool not found."
                tm = ToolMessage(content=result, tool_call_id=call["id"])
                messages.append(tm)
                history.append(tm)
            time.sleep(3)
            response = llm_with_tools.invoke(messages)

        answer = extract_text(response.content)
        history.append(response)
        print(f"\nAgent: {answer}\n")
        save_memory(trim_memory(history))           # auto-save after every turn

    return history


# ── main pipeline ──────────────────────────────────────────────
def run_pipeline(company: str, role: str):
    divider(f"Company Research Chain — {role} at {company}")
    start = time.time()

    raw               = stage1_parallel_research(company, role)
    time.sleep(2)
    snapshot, plan    = stage2_extract_structured(company, role, raw)
    time.sleep(2)
    narrative         = stage3_narrative(company, role, raw, snapshot)
    time.sleep(2)
    report_path       = stage4_save_report(company, role, snapshot, plan, narrative)

    print(f"\n  Done in {time.time()-start:.1f}s")

    divider("Summary")
    print(f"  Company    : {snapshot.name}")
    print(f"  Difficulty : {snapshot.difficulty}")
    print(f"  CTC        : {snapshot.fresher_ctc}")
    print(f"  Rounds     : {' → '.join(snapshot.interview_rounds)}")
    print(f"  Report     : {report_path}")
    return snapshot, plan


if __name__ == "__main__":
    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)

    company = input("Company: ").strip()
    role    = input("Role   : ").strip()
    if not company or not role:
        print("Both fields required.")
        exit(1)

    history = load_memory()                         # load previous sessions

    run_pipeline(company, role)

    print("\nReport saved. Ask follow-up questions or type 'done' to finish.")
    history = stage5_followup_chat(company, role, history)

    save_memory(trim_memory(history))
    print(f"\nMemory saved — {sum(1 for m in history if isinstance(m, HumanMessage))} turn(s)")
