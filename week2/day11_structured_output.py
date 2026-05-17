"""Day 11 — Structured Output: Force the LLM to Return Clean JSON
Three levels: DIY JSON prompt → JsonOutputParser → with_structured_output (Pydantic)."""

import os, time
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,            # low temp = more predictable output
    max_output_tokens=600,
)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── schemas ────────────────────────────────────────────────────
# field descriptions are read by the LLM — be specific

class CompanyProfile(BaseModel):
    name:                 str       = Field(description="Company name")
    founded:              str       = Field(description="Year the company was founded")
    headquarters:         str       = Field(description="City and country of HQ")
    tech_stack:           list[str] = Field(description="Main technologies the company uses")
    known_for:            str       = Field(description="What the company is best known for (1-2 sentences)")
    interview_rounds:     list[str] = Field(description="Interview stages in order")
    interview_difficulty: str       = Field(description="easy / medium / hard")
    fresher_ctc_lpa:      str       = Field(description="Fresher CTC range e.g. '3.5 - 6 LPA'")

class InterviewPlan(BaseModel):
    company:              str       = Field(description="Company name")
    role:                 str       = Field(description="Job role")
    priority_topics:      list[str] = Field(description="Top 5 topics to study, ordered by importance")
    skills_to_highlight:  list[str] = Field(description="Skills to emphasise in interviews")
    timeline_weeks:       int       = Field(description="Weeks of prep needed")
    daily_plan:           str       = Field(description="Short daily study routine (3-4 sentences)")
    red_flags:            list[str] = Field(description="Common mistakes freshers make")


# ── approach 1: diy json prompt (fragile) ──────────────────────
def approach1_diy_json(company: str):
    divider("Approach 1 — DIY JSON Prompt  (fragile)")

    # ask nicely — no guarantee the LLM returns valid JSON
    prompt = (f"Return ONLY a JSON object about {company}. No markdown, no extra text.\n"
              f'Format: {{"name": "", "founded": "", "hq": "", "known_for": ""}}')

    raw = llm.invoke(prompt).content
    print(f"Raw:\n{raw}\n")

    import json
    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        print(f"Parsed: {json.loads(cleaned)}")
    except json.JSONDecodeError as e:
        print(f"Parse FAILED: {e}  ← this is why DIY is fragile")


# ── approach 2: jsonoutputparser (auto-strips fences) ──────────
def approach2_json_parser(company: str):
    divider("Approach 2 — JsonOutputParser  (cleaner, no type validation)")

    # parser auto-strips markdown fences and calls json.loads()
    template = ChatPromptTemplate.from_template(
        "Return a JSON object with: name, founded, hq, known_for, interview_difficulty. "
        "Company: {company}. Return ONLY JSON."
    )
    chain = template | llm | JsonOutputParser()     # pipe: prompt → llm → parse

    result = chain.invoke({"company": company})
    print(f"Type : {type(result).__name__}")        # dict — no manual parsing needed
    print(f"Data : {result}")


# ── approach 3: with_structured_output + pydantic (gold standard) ─
def approach3_structured(company: str):
    divider("Approach 3 — with_structured_output()  (validated, guaranteed shape)")

    # LLM is forced to match CompanyProfile — Pydantic validates every field
    structured_llm = llm.with_structured_output(CompanyProfile)
    profile: CompanyProfile = structured_llm.invoke(
        f"Give me a detailed placement-focused profile of {company}."
    )

    print(f"Type        : {type(profile).__name__}")
    print(f"Company     : {profile.name}")
    print(f"Founded     : {profile.founded}")
    print(f"HQ          : {profile.headquarters}")
    print(f"Difficulty  : {profile.interview_difficulty}")
    print(f"CTC         : {profile.fresher_ctc_lpa}")
    print(f"Tech Stack  : {', '.join(profile.tech_stack)}")
    print(f"Rounds      : {' → '.join(profile.interview_rounds)}")
    return profile


# ── practical: generate a personalised interview plan ──────────
def generate_interview_plan(company: str, role: str):
    divider(f"Interview Plan — {role} at {company}")

    structured_llm = llm.with_structured_output(InterviewPlan)
    plan: InterviewPlan = structured_llm.invoke(
        f"Create a prep plan for a fresher applying for {role} at {company} in India."
    )

    print(f"Timeline : {plan.timeline_weeks} week(s)")
    print(f"\nPriority Topics:")
    for i, t in enumerate(plan.priority_topics, 1):
        print(f"  {i}. {t}")
    print(f"\nHighlight : {', '.join(plan.skills_to_highlight)}")
    print(f"\nDaily Plan:\n  {plan.daily_plan}")
    print(f"\nAvoid:")
    for r in plan.red_flags:
        print(f"  - {r}")
    return plan


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    company = input("Company: ").strip() or "Infosys"
    role    = input("Role   : ").strip() or "SDE-1"

    approach1_diy_json(company)
    time.sleep(4)

    approach2_json_parser(company)
    time.sleep(4)

    approach3_structured(company)
    time.sleep(4)

    generate_interview_plan(company, role)
