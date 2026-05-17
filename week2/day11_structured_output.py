"""
Day 11 - Structured Output: Making the LLM Return Clean JSON
=============================================================
Problem: LLM responses are free-form text.
         Hard to parse, validate, or pass into the next step of a pipeline.

Solution: Tell the LLM exactly what shape to return and validate it with Pydantic.

Three levels (worst → best):
  1. DIY JSON prompt              -> ask nicely, hope for valid JSON  (fragile)
  2. JsonOutputParser             -> auto-parse JSON, still no type checks
  3. .with_structured_output()    -> Pydantic schema, fully validated (gold standard)
"""

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
    temperature=0.1,           # low temp = more predictable / structured output
    max_output_tokens=600,
)

def divider(title=""):
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("=" * 60)


# =============================================================================
# PYDANTIC SCHEMAS
# These are the "contracts" we make with the LLM.
# Every field has a description — the LLM reads it to know what to put there.
# =============================================================================

class CompanyProfile(BaseModel):
    """Structured profile of a tech company for placement purposes."""
    name:               str        = Field(description="Company name")
    founded:            str        = Field(description="Year the company was founded")
    headquarters:       str        = Field(description="City and country of headquarters")
    tech_stack:         list[str]  = Field(description="Main technologies the company uses")
    known_for:          str        = Field(description="What the company is best known for (1-2 sentences)")
    interview_rounds:   list[str]  = Field(description="Typical interview rounds in order (e.g. Online Test, Technical, HR)")
    interview_difficulty: str      = Field(description="One of: easy / medium / hard")
    fresher_ctc_lpa:    str        = Field(description="Typical fresher CTC range in LPA (e.g. '3.5 - 6 LPA')")


class InterviewPlan(BaseModel):
    """A personalised study plan for a specific company and role."""
    company:            str        = Field(description="Company name")
    role:               str        = Field(description="Job role the candidate is applying for")
    priority_topics:    list[str]  = Field(description="Top 5 topics to study, ordered by importance")
    skills_to_highlight: list[str] = Field(description="Skills to emphasise during the interview")
    timeline_weeks:     int        = Field(description="Recommended weeks of preparation")
    daily_plan:         str        = Field(description="A short daily study routine (3-4 sentences)")
    red_flags:          list[str]  = Field(description="Common mistakes freshers make in this interview")


# =============================================================================
# APPROACH 1: DIY JSON Prompt  (fragile — for comparison only)
# The LLM might add ```json fences, extra commentary, or malformed output.
# =============================================================================

def approach1_diy_json(company: str):
    divider("Approach 1 - DIY JSON Prompt (fragile)")
    print("Ask the LLM to 'return JSON'. No guarantee it actually does.\n")

    prompt = f"""Return ONLY a JSON object about {company}. No markdown fences, no extra text.
Format: {{"name": "", "founded": "", "hq": "", "known_for": ""}}"""

    response = llm.invoke(prompt)
    raw = response.content
    print(f"Raw response:\n{raw}\n")

    # Try to parse — this often breaks in practice
    import json
    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        print(f"Parsed OK: {data}")
    except json.JSONDecodeError as e:
        print(f"Parse FAILED: {e}")
        print("This is why DIY JSON prompts are fragile.")


# =============================================================================
# APPROACH 2: JsonOutputParser (better — auto-strips fences, still no validation)
# =============================================================================

def approach2_json_parser(company: str):
    divider("Approach 2 - JsonOutputParser")
    print("LangChain strips markdown fences and parses JSON automatically.")
    print("But it still can't validate field types or required fields.\n")

    template = ChatPromptTemplate.from_template(
        "Return a JSON object with keys: name, founded, hq, known_for, interview_difficulty. "
        "Company: {company}. Return ONLY JSON."
    )

    chain = template | llm | JsonOutputParser()

    result = chain.invoke({"company": company})
    print(f"Result type : {type(result).__name__}")
    print(f"Result value: {result}")
    print("\nIt's a real Python dict — no manual parsing needed.")


# =============================================================================
# APPROACH 3: .with_structured_output()  (gold standard)
# Pydantic validates every field. Wrong type = exception before it reaches your code.
# The LLM also sees the schema description, so it fills fields more accurately.
# =============================================================================

def approach3_structured(company: str):
    divider("Approach 3 - with_structured_output() + Pydantic (gold standard)")
    print("LLM is forced to return data matching the CompanyProfile schema exactly.")
    print("Pydantic validates types. Missing required fields raise an error.\n")

    structured_llm = llm.with_structured_output(CompanyProfile)

    prompt = f"Give me a detailed placement-focused profile of {company}."
    profile: CompanyProfile = structured_llm.invoke(prompt)

    print(f"Type : {type(profile).__name__}")
    print(f"\nCompany     : {profile.name}")
    print(f"Founded     : {profile.founded}")
    print(f"HQ          : {profile.headquarters}")
    print(f"Difficulty  : {profile.interview_difficulty}")
    print(f"Fresher CTC : {profile.fresher_ctc_lpa}")
    print(f"Known For   : {profile.known_for}")
    print(f"\nTech Stack  : {', '.join(profile.tech_stack)}")
    print(f"\nInterview Rounds:")
    for i, r in enumerate(profile.interview_rounds, 1):
        print(f"  {i}. {r}")

    return profile


# =============================================================================
# PRACTICAL USE: Generate a personalised InterviewPlan
# =============================================================================

def generate_interview_plan(company: str, role: str):
    divider(f"Interview Plan: {role} at {company}")

    structured_llm = llm.with_structured_output(InterviewPlan)

    prompt = (f"Create a detailed interview preparation plan for a fresher "
              f"applying for {role} at {company} in India.")

    plan: InterviewPlan = structured_llm.invoke(prompt)

    print(f"Preparation Timeline : {plan.timeline_weeks} week(s)")
    print(f"\nPriority Topics:")
    for i, t in enumerate(plan.priority_topics, 1):
        print(f"  {i}. {t}")

    print(f"\nSkills to Highlight  : {', '.join(plan.skills_to_highlight)}")
    print(f"\nDaily Plan:\n  {plan.daily_plan}")

    print(f"\nRed Flags (avoid these):")
    for r in plan.red_flags:
        print(f"  - {r}")

    return plan


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Day 11 - Structured Output")
    print("Three approaches to making the LLM return clean, validated data.\n")

    company = input("Company to profile: ").strip() or "Infosys"
    role    = input("Role (for interview plan): ").strip() or "SDE-1"

    # Approach 1: show the problem
    approach1_diy_json(company)
    time.sleep(4)

    # Approach 2: JsonOutputParser
    approach2_json_parser(company)
    time.sleep(4)

    # Approach 3: with_structured_output (Pydantic)
    profile = approach3_structured(company)
    time.sleep(4)

    # Practical: generate a personalised plan
    plan = generate_interview_plan(company, role)

    divider("Day 11 Complete")
    print("Day  8: prompt | model | parser           (basic pipe)")
    print("Day  9: model + tools + agent loop        (live web search)")
    print("Day 10: agent + file memory               (remembers sessions)")
    print("Day 11: with_structured_output + Pydantic (clean, validated JSON)")
    print("Day 12: RunnableParallel + LCEL chains    (parallel pipelines)")
    print("=" * 60)
