"""
Day 12 - LCEL Chains: Parallel Execution and Composition
=========================================================
Day 8 showed the basic pipe:  prompt | llm | parser
Day 12 goes deeper:

  RunnableParallel   -> run multiple chains simultaneously
  RunnableLambda     -> wrap any Python function as a chain step
  RunnablePassthrough-> pass the input through unchanged (useful for branching)
  itemgetter         -> pull one key from a dict inside a chain

Why chains?
  Without chains: call A, wait, call B, wait, call C, wait  = slow, messy
  With chains   : define the pipeline once, invoke once, LangChain handles the rest
"""

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
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=600,
)

_tavily = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"), max_results=3)

def divider(title=""):
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("=" * 60)

def search(query: str) -> str:
    """Thin wrapper: Tavily search → joined text."""
    results = _tavily.invoke({"query": query})
    if isinstance(results, list):
        return "\n\n".join(r.get("content", "") for r in results[:2])
    return str(results)


# =============================================================================
# PHASE 1 - Chain Primitives Explained (no API calls)
# =============================================================================

def phase1_explain():
    divider("PHASE 1 - LCEL Chain Primitives")
    print("""
LCEL (LangChain Expression Language) uses the | pipe operator
to connect components into chains.

  chain = step_A | step_B | step_C
  result = chain.invoke({"key": "value"})

Each step receives the output of the previous step as its input.

── Primitives ────────────────────────────────────────────────

  RunnableParallel({"a": chain_a, "b": chain_b})
    Runs chain_a and chain_b at the same time.
    Output: {"a": result_a, "b": result_b}
    Use when: two independent searches / two independent LLM calls.

  RunnableLambda(fn)
    Wraps any Python function as a chain step.
    Output: whatever fn(input) returns.
    Use when: you need custom logic between LLM calls.

  RunnablePassthrough()
    Passes the input through unchanged.
    Use when: you want to keep original data alongside new results.

  itemgetter("key")
    Extracts one key from a dict at that point in the chain.
    Use when: you only want one field from the previous step's output.

── Example ───────────────────────────────────────────────────

  chain = (
      RunnableParallel({
          "interview":   RunnableLambda(lambda x: search(x["company"] + " interview")),
          "salary":      RunnableLambda(lambda x: search(x["company"] + " salary")),
          "company_in":  RunnablePassthrough(),   # keep original input
      })
      | RunnableLambda(combine_results)           # merge the three outputs
      | summary_prompt                            # format for LLM
      | llm                                       # call LLM
      | StrOutputParser()                         # extract text
  )
""")


# =============================================================================
# PHASE 2 - Parallel Search Chain
# Two Tavily searches run simultaneously, then merged and summarised by the LLM
# =============================================================================

def phase2_parallel_chain(company: str):
    divider(f"PHASE 2 - Parallel Search Chain  [{company}]")
    print("Running interview process search + salary search in parallel...")
    print("(Both searches fire at the same time — faster than sequential)\n")

    # Step 1: run both searches in parallel
    parallel_search = RunnableParallel({
        "interview_info": RunnableLambda(
            lambda x: search(f"{x['company']} interview process rounds fresher 2024")
        ),
        "salary_info": RunnableLambda(
            lambda x: search(f"{x['company']} fresher salary CTC LPA 2024 India")
        ),
        "passthrough": RunnablePassthrough(),   # keeps {"company": "..."} available downstream
    })

    # Step 2: merge the search results into a single prompt
    def merge(data: dict) -> dict:
        return {
            "company":        data["passthrough"]["company"],
            "interview_info": data["interview_info"][:800],
            "salary_info":    data["salary_info"][:800],
        }

    # Step 3: summarise with the LLM
    summary_prompt = ChatPromptTemplate.from_template("""
You are a placement advisor. Based on the research below, give a crisp summary
for a fresher applying at {company}.

Interview Info:
{interview_info}

Salary Info:
{salary_info}

Summarise in 4-5 bullet points covering: rounds, difficulty, CTC range, key tips.
""")

    # Assemble the chain
    research_chain = (
        parallel_search
        | RunnableLambda(merge)
        | summary_prompt
        | llm
        | StrOutputParser()
    )

    start = time.time()
    result = research_chain.invoke({"company": company})
    elapsed = time.time() - start

    print(f"Chain completed in {elapsed:.1f}s\n")
    print(result)
    return result


# =============================================================================
# PHASE 3 - Multi-Step Chain: Research → Profile → Plan
# Chain 1: parallel search → summary
# Chain 2: summary → structured profile (from Day 11)
# Chain 3: profile → interview advice
# All connected with | into a single callable pipeline
# =============================================================================

class QuickProfile(BaseModel):
    difficulty:   str       = Field(description="easy / medium / hard")
    rounds:       list[str] = Field(description="Interview rounds in order")
    ctc_range:    str       = Field(description="Fresher CTC range in LPA")
    top_tip:      str       = Field(description="Single most important preparation tip")


def phase3_multi_step_chain(company: str, role: str):
    divider(f"PHASE 3 - Multi-Step Chain  [{role} at {company}]")
    print("Three chained steps: search → structured profile → personalised advice\n")

    # Chain A: search → summary text
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
        "Summarise key facts about {role} interviews at {company} "
        "based on: {research}\n\nBe factual and concise."
    )

    summary_chain = (
        search_step
        | RunnableLambda(build_summary_input)
        | summary_prompt
        | llm
        | StrOutputParser()
    )

    # Chain B: summary text → structured QuickProfile
    structured_llm = llm.with_structured_output(QuickProfile)

    def to_profile_input(summary_text):
        return f"Extract structured placement facts from this summary:\n{summary_text}"

    profile_chain = RunnableLambda(to_profile_input) | structured_llm

    # Chain C: profile → personalised advice
    advice_prompt = ChatPromptTemplate.from_template("""
Given this interview profile for {role} at {company}:
  Difficulty : {difficulty}
  Rounds     : {rounds}
  CTC Range  : {ctc_range}
  Top Tip    : {top_tip}

Write a 3-point personalised preparation strategy for a fresher.
""")

    print("Step 1: Running parallel searches...")
    time.sleep(1)
    summary = summary_chain.invoke({"company": company, "role": role})
    print(f"  Search + summary done ({len(summary)} chars)\n")

    print("Step 2: Extracting structured profile...")
    time.sleep(3)
    profile: QuickProfile = profile_chain.invoke(summary)
    print(f"  Profile: difficulty={profile.difficulty}, ctc={profile.ctc_range}\n")

    print("Step 3: Generating personalised advice...")
    time.sleep(3)
    advice_input = {
        "role":       role,
        "company":    company,
        "difficulty": profile.difficulty,
        "rounds":     ", ".join(profile.rounds),
        "ctc_range":  profile.ctc_range,
        "top_tip":    profile.top_tip,
    }
    advice = (advice_prompt | llm | StrOutputParser()).invoke(advice_input)

    divider("Final Output")
    print(f"Difficulty : {profile.difficulty}")
    print(f"Rounds     : {' → '.join(profile.rounds)}")
    print(f"CTC Range  : {profile.ctc_range}")
    print(f"Top Tip    : {profile.top_tip}")
    print(f"\nPersonalised Advice:\n{advice}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Day 12 - LCEL Chains: Parallel Execution and Composition")
    print("Building pipelines that run fast and stay readable.\n")

    company = input("Company: ").strip() or "Wipro"
    role    = input("Role   : ").strip() or "SDE-1"

    phase1_explain()
    input("\nPress Enter to run Phase 2 (parallel search chain)...")

    phase2_parallel_chain(company)

    print("\n\nMoving to Phase 3 in 5 seconds...")
    time.sleep(5)

    phase3_multi_step_chain(company, role)

    divider("Day 12 Complete")
    print("Day  8: prompt | llm | parser             (single pipe)")
    print("Day 12: RunnableParallel + multi-step     (parallel pipelines)")
    print("Day 13: output parsers + retry + fallback (robustness)")
    print("=" * 60)
