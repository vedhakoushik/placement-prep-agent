"""Day 13-14 — Mini Project: Company Research Chain
Input : company name + role
Chain 1: Tavily searches (news, tech stack, interview experiences)
Chain 2: synthesises results into a CompanyProfile Pydantic object
Chain 3: generates 10 role-specific interview questions
Output: saves everything to week2/profiles/{company_name}_profile.json
        This JSON becomes Week 3's input data for RAG / ChromaDB."""

import os, json
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.output_parsers import PydanticOutputParser
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

PROFILES_DIR = Path(__file__).parent / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=1500,
)

tavily = TavilySearchResults(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=4,
)


# ── schema ─────────────────────────────────────────────────────
class CompanyProfile(BaseModel):
    company_name:     str                            = Field(description="Full company name")
    tech_stack:       list[str]                      = Field(description="Technologies the company primarily uses")
    interview_rounds: list[str]                      = Field(description="Interview stages in order for freshers")
    key_topics:       list[str]                      = Field(description="Top topics a fresher must study for this company")
    difficulty:       Literal["low","medium","high"] = Field(description="Overall interview difficulty")
    fresher_ctc:      str                            = Field(description="Typical fresher CTC range in LPA")
    recent_news:      str                            = Field(description="One recent fact about the company (hiring, tech, etc.)")


# ── chain 1: tavily web research ───────────────────────────────
def chain1_research(company: str, role: str) -> dict:
    divider("Chain 1 — Web Research")

    queries = {
        "interview":  f"{company} {role} interview process rounds fresher 2024 2025",
        "tech_stack": f"{company} tech stack technologies used engineering team",
        "experience": f"{company} {role} fresher interview experience Glassdoor",
        "news":       f"{company} latest news hiring 2025",
    }

    raw = {}
    for key, q in queries.items():
        print(f"  Searching: {q[:60]}...")
        results = tavily.invoke(q)
        raw[key] = "\n\n".join(r.get("content", "") for r in results[:3]) if isinstance(results, list) else str(results)
        print(f"    Got {len(raw[key])} chars")

    return raw


# ── chain 2: synthesise into CompanyProfile ────────────────────
def chain2_synthesise(company: str, role: str, raw: dict) -> CompanyProfile:
    divider("Chain 2 — Synthesise into CompanyProfile")

    parser = PydanticOutputParser(pydantic_object=CompanyProfile)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a placement advisor. Extract structured data from research. "
                   "Follow the output format instructions exactly."),
        ("human",  "Synthesise a CompanyProfile for {company} ({role} role) from this research:\n\n"
                   "Interview process:\n{interview}\n\n"
                   "Tech stack:\n{tech_stack}\n\n"
                   "Candidate experiences:\n{experience}\n\n"
                   "Recent news:\n{news}\n\n"
                   "{format_instructions}"),
    ])

    chain   = prompt | llm | parser
    profile = chain.invoke({
        "company":             company,
        "role":                role,
        "interview":           raw["interview"][:800],
        "tech_stack":          raw["tech_stack"][:600],
        "experience":          raw["experience"][:600],
        "news":                raw["news"][:400],
        "format_instructions": parser.get_format_instructions(),
    })

    print(f"  Extracted: difficulty={profile.difficulty}, ctc={profile.fresher_ctc}")
    print(f"  Rounds    : {' → '.join(profile.interview_rounds)}")
    print(f"  Topics    : {', '.join(profile.key_topics[:3])}...")
    return profile


# ── chain 3: generate 10 interview questions ───────────────────
def chain3_questions(company: str, role: str, profile: CompanyProfile) -> list[str]:
    divider("Chain 3 — Generate 10 Interview Questions")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a technical interviewer at a top tech company in India."),
        ("human",  "Generate exactly 10 interview questions for a fresher applying for "
                   "{role} at {company}.\n\n"
                   "Profile:\n"
                   "  Tech stack     : {tech_stack}\n"
                   "  Difficulty     : {difficulty}\n"
                   "  Key topics     : {key_topics}\n\n"
                   "Mix: 4 DSA/technical, 3 concept-based, 2 project/experience, 1 HR.\n"
                   "Number each question 1-10. Return only the questions, no answers."),
    ])

    chain  = prompt | llm | StrOutputParser()
    output = chain.invoke({
        "company":    company,
        "role":       role,
        "tech_stack": ", ".join(profile.tech_stack),
        "difficulty": profile.difficulty,
        "key_topics": ", ".join(profile.key_topics),
    })

    # parse numbered lines into a list
    questions = [
        line.strip()
        for line in output.split("\n")
        if line.strip() and line.strip()[0].isdigit()
    ][:10]

    for q in questions:
        print(f"  {q}")
    return questions


# ── save to json ───────────────────────────────────────────────
def save_profile(company: str, role: str, profile: CompanyProfile,
                 questions: list[str], raw: dict) -> Path:
    divider("Saving Profile")

    data = {
        **profile.model_dump(),             # all CompanyProfile fields
        "role":                role,
        "interview_questions": questions,
        "raw_research":        {k: v[:500] for k, v in raw.items()},  # truncated for size
    }

    filename = f"{company.lower().replace(' ', '_')}_profile.json"
    path     = PROFILES_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  Saved → {path}")
    print(f"  Fields: {list(data.keys())}")
    print("  This file is Week 3's input for RAG / ChromaDB.")
    return path


# ── full pipeline ──────────────────────────────────────────────
def run_pipeline(company: str, role: str) -> Path:
    divider(f"Company Research Chain — {role} at {company}")

    raw       = chain1_research(company, role)
    profile   = chain2_synthesise(company, role, raw)
    questions = chain3_questions(company, role, profile)
    path      = save_profile(company, role, profile, questions, raw)

    divider("Done")
    print(f"  Company    : {profile.company_name}")
    print(f"  Difficulty : {profile.difficulty}")
    print(f"  CTC        : {profile.fresher_ctc}")
    print(f"  Questions  : {len(questions)}")
    print(f"  Output     : {path}")
    return path


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not set in .env")
        exit(1)
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set in .env")
        exit(1)

    company = input("Company: ").strip()
    role    = input("Role   : ").strip()

    if not company or not role:
        print("Both fields required.")
        exit(1)

    run_pipeline(company, role)
