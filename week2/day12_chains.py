"""Day 12 — LCEL Chains: Parallel Execution and Composition
RunnableParallel fires multiple chains at once. RunnableLambda wraps any Python function."""

import os, time
from operator import itemgetter
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnableLambda, RunnablePassthrough
from langchain_tavily import TavilySearch

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=600,
)

_tavily = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"), max_results=3)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

def search(query: str) -> str:
    """Tavily search → joined text."""
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:2])
    return str(results)


# ── phase 1: primitives overview (no api calls) ────────────────
def phase1_explain():
    divider("PHASE 1 — LCEL Chain Primitives")
    print("  prompt | llm | parser           → basic pipe (Day 8)")
    print()
    print("  RunnableParallel({'a': c1, 'b': c2})")
    print("    → runs c1 and c2 at the same time, returns {'a': r1, 'b': r2}")
    print()
    print("  RunnableLambda(fn)")
    print("    → wraps any Python function as a chain step")
    print()
    print("  RunnablePassthrough()")
    print("    → passes the input through unchanged (useful for keeping original data)")
    print()
    print("  Chain: parallel_search | merge_fn | prompt | llm | parser")
    print("         ↑ fires both searches at once")


# ── phase 2: parallel search chain ─────────────────────────────
def phase2_parallel_chain(company: str):
    divider(f"PHASE 2 — Parallel Search Chain  [{company}]")
    print("Two Tavily searches fire simultaneously, merged, then summarised by LLM.\n")

    # step 1: run both searches at the same time
    parallel_search = RunnableParallel({
        "interview": RunnableLambda(
            lambda x: search(f"{x['company']} interview process rounds 2024")
        ),
        "salary": RunnableLambda(
            lambda x: search(f"{x['company']} fresher salary CTC LPA 2024 India")
        ),
        "orig": RunnablePassthrough(),              # keep {"company": "..."} for later steps
    })

    # step 2: merge three outputs into one dict for the prompt
    def merge(data: dict) -> dict:
        return {
            "company":        data["orig"]["company"],
            "interview_info": data["interview"][:800],
            "salary_info":    data["salary"][:800],
        }

    # step 3: summarise with llm
    summary_prompt = ChatPromptTemplate.from_template(
        "You are a placement advisor. Summarise for a fresher at {company}.\n\n"
        "Interview data:\n{interview_info}\n\nSalary data:\n{salary_info}\n\n"
        "Give 4-5 bullet points: rounds, difficulty, CTC range, key tips."
    )

    # assemble the full chain with |
    chain = parallel_search | RunnableLambda(merge) | summary_prompt | llm | StrOutputParser()

    start  = time.time()
    result = chain.invoke({"company": company})
    print(f"Done in {time.time() - start:.1f}s\n")
    print(result)
    return result


# ── phase 3: multi-step chain — search → profile → advice ──────
class QuickProfile(BaseModel):
    difficulty: str       = Field(description="easy / medium / hard")
    rounds:     list[str] = Field(description="Interview rounds in order")
    ctc_range:  str       = Field(description="Fresher CTC range in LPA")
    top_tip:    str       = Field(description="Single most important prep tip")


def phase3_multi_step(company: str, role: str):
    divider(f"PHASE 3 — Multi-Step Chain  [{role} at {company}]")
    print("Step 1: parallel search  →  Step 2: structured profile  →  Step 3: advice\n")

    # step 1: parallel search
    search_step = RunnableParallel({
        "interview": RunnableLambda(lambda x: search(f"{x['company']} {x['role']} interview 2024")),
        "salary":    RunnableLambda(lambda x: search(f"{x['company']} {x['role']} salary LPA 2024")),
        "orig":      RunnablePassthrough(),
    })

    def build_summary_input(data):
        return {
            "company":  data["orig"]["company"],
            "role":     data["orig"]["role"],
            "research": data["interview"][:600] + "\n\n" + data["salary"][:600],
        }

    summary_prompt = ChatPromptTemplate.from_template(
        "Summarise key placement facts about {role} at {company}.\nData: {research}"
    )
    summary_chain = (
        search_step | RunnableLambda(build_summary_input)
        | summary_prompt | llm | StrOutputParser()
    )

    # step 2: extract structured profile from the summary text
    def to_profile_input(text): return f"Extract placement facts:\n{text}"
    profile_chain = RunnableLambda(to_profile_input) | llm.with_structured_output(QuickProfile)

    # step 3: personalised advice from profile
    advice_prompt = ChatPromptTemplate.from_template(
        "Interview profile for {role} at {company}:\n"
        "  Difficulty: {difficulty}\n  Rounds: {rounds}\n"
        "  CTC: {ctc_range}\n  Top tip: {top_tip}\n\n"
        "Write 3 concrete prep points for a fresher."
    )

    # run the three steps in sequence
    print("Searching...")
    summary = summary_chain.invoke({"company": company, "role": role})
    time.sleep(3)

    print("Extracting profile...")
    profile: QuickProfile = profile_chain.invoke(summary)
    time.sleep(3)

    print("Generating advice...\n")
    advice = (advice_prompt | llm | StrOutputParser()).invoke({
        "role": role, "company": company,
        "difficulty": profile.difficulty, "rounds": ", ".join(profile.rounds),
        "ctc_range": profile.ctc_range, "top_tip": profile.top_tip,
    })

    divider("Output")
    print(f"Difficulty : {profile.difficulty}")
    print(f"Rounds     : {' → '.join(profile.rounds)}")
    print(f"CTC        : {profile.ctc_range}")
    print(f"\n{advice}")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    company = input("Company: ").strip() or "Wipro"
    role    = input("Role   : ").strip() or "SDE-1"

    phase1_explain()
    phase2_parallel_chain(company)
    print("\nMoving to Phase 3 in 5 seconds...")
    time.sleep(5)

    phase3_multi_step(company, role)
