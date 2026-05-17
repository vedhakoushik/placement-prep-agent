"""
Day 14 - Week 2 Capstone: Full Company Research Chain
======================================================
This is the Week 2 payoff. Everything from Days 8-13 combined:

  Day  8: LCEL pipe  (prompt | llm | parser)
  Day  9: Tools + Tavily web search
  Day 10: Persistent memory (load/save JSON)
  Day 11: Structured output with Pydantic schemas
  Day 12: RunnableParallel chains
  Day 13: Retry + fallback robustness

Input : company name + role
Output: a complete markdown research report saved to week2/reports/<company>.md

The report covers: company profile, interview process, salary, prep plan, culture.
It is generated from live web data — not from the LLM's training data.
"""

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


# ── helpers ───────────────────────────────────────────────────────────────────
def divider(title=""):
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("=" * 60)

def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)

def web_search(query: str, n: int = 3) -> str:
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:n])
    return str(results)


# =============================================================================
# SCHEMAS  (Day 11)
# =============================================================================

class CompanySnapshot(BaseModel):
    name:             str       = Field(description="Company name")
    founded:          str       = Field(description="Year founded")
    headquarters:     str       = Field(description="City and country")
    tech_stack:       list[str] = Field(description="Main technologies used")
    interview_rounds: list[str] = Field(description="Interview stages in order")
    difficulty:       str       = Field(description="easy / medium / hard")
    fresher_ctc:      str       = Field(description="Fresher CTC range in LPA")
    culture_rating:   str       = Field(description="Work culture rating: excellent / good / average / poor")

class PrepPlan(BaseModel):
    priority_topics:     list[str] = Field(description="Top 5 topics to study")
    skills_to_highlight: list[str] = Field(description="Skills to emphasise in interviews")
    timeline_weeks:      int       = Field(description="Weeks of preparation needed")
    daily_routine:       str       = Field(description="Concise daily study routine (2-3 sentences)")
    avoid:               list[str] = Field(description="3 common mistakes to avoid")


# =============================================================================
# MEMORY LAYER  (Day 10)
# =============================================================================

def load_memory() -> list:
    if not MEMORY_FILE.exists():
        return []
    try:
        records = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        msgs = []
        for r in records:
            if r["role"] == "human":
                msgs.append(HumanMessage(content=r["content"]))
            elif r["role"] == "ai":
                msgs.append(AIMessage(content=r["content"]))
        return msgs
    except:
        return []

def save_memory(history: list):
    records = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            records.append({"role": "human", "content": extract_text(msg.content)})
        elif isinstance(msg, AIMessage):
            text = extract_text(msg.content)
            if text.strip():
                records.append({"role": "ai", "content": text})
    MEMORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

def trim_memory(history: list, max_turns: int = MAX_TURNS) -> list:
    human_idx = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(human_idx) <= max_turns:
        return history
    return history[human_idx[-max_turns]:]


# =============================================================================
# TOOLS  (Day 9)
# =============================================================================

@tool
def search_interview_process(company: str) -> str:
    """Search the web for the current interview process at a company."""
    return web_search(f"{company} interview process rounds fresher 2024")

@tool
def search_salary_info(company: str, role: str) -> str:
    """Search the web for fresher salary and CTC for a role at a company."""
    return web_search(f"{company} {role} fresher salary CTC LPA 2024 India")

@tool
def search_preparation_tips(company: str, role: str) -> str:
    """Search for preparation tips and interview experiences."""
    return web_search(f"{company} {role} interview preparation tips experience 2024")

@tool
def search_company_culture(company: str) -> str:
    """Search for work culture, work-life balance, and employee reviews."""
    return web_search(f"{company} work culture employee review growth 2024")

ALL_TOOLS = [search_interview_process, search_salary_info,
             search_preparation_tips, search_company_culture]
TOOLS_MAP  = {t.name: t for t in ALL_TOOLS}


# =============================================================================
# STAGE 1: Parallel Web Research  (Day 12 — RunnableParallel)
# Fires 4 searches simultaneously to collect raw data
# =============================================================================

def stage1_parallel_research(company: str, role: str) -> dict:
    print("  Stage 1: Parallel web research (4 searches at once)...")

    parallel = RunnableParallel({
        "interview":  RunnableLambda(lambda x: web_search(f"{x['company']} interview process rounds 2024")),
        "salary":     RunnableLambda(lambda x: web_search(f"{x['company']} {x['role']} salary CTC LPA 2024")),
        "prep_tips":  RunnableLambda(lambda x: web_search(f"{x['company']} {x['role']} preparation tips 2024")),
        "culture":    RunnableLambda(lambda x: web_search(f"{x['company']} work culture review 2024")),
    })

    raw = parallel.invoke({"company": company, "role": role})
    chars = sum(len(v) for v in raw.values())
    print(f"     Collected {chars:,} chars of raw web data")
    return raw


# =============================================================================
# STAGE 2: Structured Extraction  (Day 11 — with_structured_output)
# LLM reads the raw data and extracts clean, validated JSON
# =============================================================================

def stage2_extract_structured(company: str, role: str, raw: dict) -> tuple[CompanySnapshot, PrepPlan]:
    print("  Stage 2: Extracting structured profile and prep plan...")

    snippet = lambda k: raw[k][:700]

    # Extract CompanySnapshot
    snap_llm = llm.with_structured_output(CompanySnapshot)
    snap_prompt = (
        f"Extract a placement-focused company snapshot for {company} from this web data.\n\n"
        f"Interview data:\n{snippet('interview')}\n\n"
        f"Salary data:\n{snippet('salary')}\n\n"
        f"Culture data:\n{snippet('culture')}"
    )

    time.sleep(3)
    try:
        snapshot: CompanySnapshot = snap_llm.invoke(snap_prompt)
    except Exception as e:
        print(f"     Snapshot extraction failed ({e}), using fallback values.")
        snapshot = CompanySnapshot(
            name=company, founded="N/A", headquarters="India",
            tech_stack=["N/A"], interview_rounds=["Online Test", "Technical", "HR"],
            difficulty="medium", fresher_ctc="3-6 LPA", culture_rating="good"
        )

    # Extract PrepPlan
    plan_llm = llm.with_structured_output(PrepPlan)
    plan_prompt = (
        f"Create a prep plan for {role} at {company} based on this data.\n\n"
        f"Prep tips:\n{snippet('prep_tips')}\n\n"
        f"Interview process:\n{snippet('interview')}"
    )

    time.sleep(3)
    try:
        prep_plan: PrepPlan = plan_llm.invoke(plan_prompt)
    except Exception as e:
        print(f"     Prep plan extraction failed ({e}), using fallback values.")
        prep_plan = PrepPlan(
            priority_topics=["DSA", "OOP", "DBMS", "OS", "CN"],
            skills_to_highlight=["Problem solving", "Communication"],
            timeline_weeks=4,
            daily_routine="Study DSA for 2 hours, review concepts for 1 hour, solve 2 problems.",
            avoid=["Not practicing mock interviews", "Skipping HR prep", "Ignoring aptitude"]
        )

    print(f"     Snapshot: difficulty={snapshot.difficulty}, CTC={snapshot.fresher_ctc}")
    print(f"     Plan    : {prep_plan.timeline_weeks} weeks, {len(prep_plan.priority_topics)} topics")
    return snapshot, prep_plan


# =============================================================================
# STAGE 3: Narrative Generation  (Day 8 — basic LCEL)
# LLM writes the readable sections from the structured data + raw research
# =============================================================================

def stage3_generate_narrative(company: str, role: str,
                               raw: dict, snapshot: CompanySnapshot) -> dict:
    print("  Stage 3: Generating narrative sections...")

    def section(prompt_text: str) -> str:
        return (ChatPromptTemplate.from_template("{text}") | llm | StrOutputParser()).invoke(
            {"text": prompt_text}
        )

    intro_prompt = (
        f"Write a 3-sentence intro for a placement report on {role} at {company}. "
        f"Mention: difficulty ({snapshot.difficulty}), CTC ({snapshot.fresher_ctc}), "
        f"and one standout fact from: {raw['culture'][:300]}"
    )
    time.sleep(3)
    intro = section(intro_prompt)

    advice_prompt = (
        f"Based on this research, write 4 concrete tips for a fresher applying to {role} at {company}:\n"
        f"{raw['prep_tips'][:600]}\nFormat as a numbered list."
    )
    time.sleep(3)
    tips = section(advice_prompt)

    print("     Narrative sections ready")
    return {"intro": intro, "tips": tips}


# =============================================================================
# STAGE 4: Build and Save Markdown Report
# =============================================================================

def stage4_build_report(company: str, role: str,
                         snapshot: CompanySnapshot, prep_plan: PrepPlan,
                         narrative: dict) -> Path:
    print("  Stage 4: Writing markdown report...")

    rounds_md  = "\n".join(f"{i+1}. {r}" for i, r in enumerate(snapshot.interview_rounds))
    topics_md  = "\n".join(f"- {t}" for t in prep_plan.priority_topics)
    skills_md  = ", ".join(prep_plan.skills_to_highlight)
    avoid_md   = "\n".join(f"- {a}" for a in prep_plan.avoid)

    report = f"""# Placement Research Report
## {role} at {snapshot.name}

---

### Overview
{narrative['intro']}

| Field | Detail |
|---|---|
| Founded | {snapshot.founded} |
| Headquarters | {snapshot.headquarters} |
| Interview Difficulty | {snapshot.difficulty.title()} |
| Fresher CTC | {snapshot.fresher_ctc} |
| Work Culture | {snapshot.culture_rating.title()} |
| Prep Timeline | {prep_plan.timeline_weeks} week(s) |

---

### Tech Stack
{', '.join(snapshot.tech_stack)}

---

### Interview Process
{rounds_md}

---

### Preparation Plan

**Priority Topics**
{topics_md}

**Skills to Highlight**
{skills_md}

**Daily Routine**
{prep_plan.daily_routine}

**Common Mistakes to Avoid**
{avoid_md}

---

### Expert Tips (from real candidate experiences)
{narrative['tips']}

---

*Generated by Placement Prep Agent — Week 2 Capstone*
*Data sourced from live web search via Tavily*
"""

    safe_name = company.lower().replace(" ", "_")
    out_path = REPORTS_DIR / f"{safe_name}_{role.lower().replace(' ', '_')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"     Report saved: {out_path}")
    return out_path


# =============================================================================
# STAGE 5: Follow-up Chat with Memory  (Day 10)
# After generating the report, user can ask follow-up questions.
# The agent remembers the company/role context across sessions.
# =============================================================================

def stage5_followup_chat(company: str, role: str, history: list):
    divider("STAGE 5 - Follow-up Chat (memory-enabled)")
    print(f"Context: {role} at {company}")
    print("Ask anything to dig deeper. Type 'done' to finish and save memory.\n")

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system = SystemMessage(content=(
        f"You are a placement advisor. The user just researched {role} at {company}. "
        "Answer follow-up questions using tools for live data. Be concise and practical."
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

        print("\n[researching...]\n")
        response = llm_with_tools.invoke(messages)

        rounds = 0
        while response.tool_calls and rounds < 3:
            rounds += 1
            messages.append(response)
            history.append(response)
            for call in response.tool_calls:
                print(f"  [searching: {call['name']}]")
                fn = TOOLS_MAP.get(call["name"])
                result = fn.invoke(call["args"]) if fn else "Tool not found."
                tm = ToolMessage(content=result, tool_call_id=call["id"])
                messages.append(tm)
                history.append(tm)
            time.sleep(3)
            response = llm_with_tools.invoke(messages)

        answer = extract_text(response.content)
        history.append(response)
        print(f"Agent: {answer}\n")
        save_memory(trim_memory(history))

    return history


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_full_pipeline(company: str, role: str):
    divider(f"Company Research Chain: {role} at {company}")
    print("Running all 4 research stages...\n")

    start = time.time()

    # Stage 1: parallel web research
    raw = stage1_parallel_research(company, role)
    time.sleep(2)

    # Stage 2: structured extraction
    snapshot, prep_plan = stage2_extract_structured(company, role, raw)
    time.sleep(2)

    # Stage 3: narrative generation
    narrative = stage3_generate_narrative(company, role, raw, snapshot)
    time.sleep(2)

    # Stage 4: save report
    report_path = stage4_build_report(company, role, snapshot, prep_plan, narrative)

    elapsed = time.time() - start
    print(f"\nAll stages done in {elapsed:.1f}s")

    # Show summary
    divider("Report Summary")
    print(f"Company    : {snapshot.name}")
    print(f"Role       : {role}")
    print(f"Difficulty : {snapshot.difficulty}")
    print(f"CTC Range  : {snapshot.fresher_ctc}")
    print(f"Rounds     : {' → '.join(snapshot.interview_rounds)}")
    print(f"\nReport saved to: {report_path}")

    return snapshot, prep_plan


if __name__ == "__main__":
    print("Day 14 - Week 2 Capstone: Full Company Research Chain")
    print("Combining Days 8-13: chains + tools + memory + structured output + robustness\n")

    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)

    company = input("Company to research: ").strip()
    role    = input("Role you are applying for: ").strip()

    if not company or not role:
        print("Both fields required.")
        exit(1)

    # Load memory from previous sessions
    history = load_memory()

    # Run the full pipeline
    snapshot, prep_plan = run_full_pipeline(company, role)

    # Follow-up chat
    print("\n\nThe report is saved. You can now ask follow-up questions.")
    history = stage5_followup_chat(company, role, history)

    # Save memory
    save_memory(trim_memory(history))
    turns = sum(1 for m in history if isinstance(m, HumanMessage))

    divider("Week 2 Complete!")
    print(f"Memory saved: {turns} turn(s) in {MEMORY_FILE.name}")
    print(f"Report at   : {(Path(__file__).parent / 'reports')}")
    print()
    print("Week 2 recap:")
    print("  Day  8: LCEL basics          prompt | llm | parser")
    print("  Day  9: Tools + Tavily       live web search agent")
    print("  Day 10: Persistent memory    remembers across sessions")
    print("  Day 11: Structured output    Pydantic-validated JSON")
    print("  Day 12: Parallel chains      RunnableParallel pipelines")
    print("  Day 13: Robustness           retry + fallback + safe_invoke")
    print("  Day 14: Capstone             full research chain + report")
    print()
    print("Week 3: Embeddings + ChromaDB + RAG -> Company Intelligence Store")
    print("=" * 60)
