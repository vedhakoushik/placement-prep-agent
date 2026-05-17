"""
Day 13 - Robustness: Parsers, Retries, and Fallbacks
=====================================================
Real agents fail. LLMs hallucinate, APIs rate-limit, JSON is malformed.
This script builds three layers of defense:

  Layer 1: PydanticOutputParser  - inject the schema into the prompt itself
  Layer 2: Retry logic           - retry on parse failure (manual + OutputFixingParser)
  Layer 3: Fallback chains       - if chain A fails, run chain B automatically

After Day 13 you know how to build agents that degrade gracefully
instead of crashing on the first bad response.
"""

import os, json, time
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableLambda

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=600,
)

# Deliberately less reliable model config for showing failures
llm_strict = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.0,
    max_output_tokens=600,
)

def divider(title=""):
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("=" * 60)


# =============================================================================
# SHARED SCHEMA
# =============================================================================

class PrepSummary(BaseModel):
    """Concise interview preparation summary."""
    company:     str       = Field(description="Company name")
    difficulty:  str       = Field(description="Interview difficulty: easy, medium, or hard")
    rounds:      list[str] = Field(description="Interview rounds in order (2-5 items)")
    top_topics:  list[str] = Field(description="Top 3 DSA/tech topics to study")
    ctc_lpa:     str       = Field(description="Fresher CTC range e.g. '4-6 LPA'")


# =============================================================================
# LAYER 1: PydanticOutputParser
# Difference from with_structured_output():
#   with_structured_output  -> LangChain + model API decide the schema injection
#   PydanticOutputParser     -> YOU inject format instructions directly in the prompt
#                              Useful when you need full control over the prompt text
# =============================================================================

def layer1_pydantic_output_parser(company: str):
    divider("LAYER 1 - PydanticOutputParser (schema injected into prompt)")
    print("The parser generates format instructions that are added to the prompt.")
    print("The LLM reads those instructions and returns JSON accordingly.\n")

    parser = JsonOutputParser(pydantic_object=PrepSummary)

    prompt = ChatPromptTemplate.from_template(
        "Give interview prep info for {company}.\n\n"
        "{format_instructions}\n\n"
        "Return ONLY the JSON object. No markdown fences."
    )

    chain = prompt | llm | parser

    # Show what the format instructions look like
    instructions = parser.get_format_instructions()
    print("Format instructions injected into prompt:\n")
    print(instructions[:400] + "...\n")

    result = chain.invoke({
        "company": company,
        "format_instructions": instructions,
    })

    print("Parsed result:")
    print(f"  Company    : {result.get('company')}")
    print(f"  Difficulty : {result.get('difficulty')}")
    print(f"  Rounds     : {result.get('rounds')}")
    print(f"  Top Topics : {result.get('top_topics')}")
    print(f"  CTC        : {result.get('ctc_lpa')}")
    return result


# =============================================================================
# LAYER 2: Retry Logic
# Strategy: try with_structured_output first; if it raises, retry up to N times.
# Each retry we slightly rephrase the prompt to nudge the LLM.
# =============================================================================

def layer2_retry(company: str, max_retries: int = 3):
    divider("LAYER 2 - Manual Retry Logic")
    print(f"Try with_structured_output up to {max_retries} times. Fall back to raw text.\n")

    structured_llm = llm_strict.with_structured_output(PrepSummary)

    prompts = [
        f"Provide a placement prep summary for {company} in India.",
        f"Give me structured interview prep details for {company}. Include difficulty, rounds, and CTC.",
        f"For a fresher applying at {company}: what are the interview rounds, difficulty, top topics, and CTC?",
    ]

    last_error = None
    for attempt, prompt_text in enumerate(prompts[:max_retries], 1):
        try:
            print(f"  Attempt {attempt}: '{prompt_text[:60]}...'")
            result: PrepSummary = structured_llm.invoke(prompt_text)
            print(f"  -> SUCCESS on attempt {attempt}")
            print(f"     difficulty={result.difficulty}, ctc={result.ctc_lpa}")
            return result
        except (ValidationError, Exception) as e:
            last_error = e
            print(f"  -> FAILED: {type(e).__name__}: {str(e)[:60]}")
            if attempt < max_retries:
                print(f"     Retrying in 3s...")
                time.sleep(3)

    print(f"\nAll {max_retries} attempts failed. Last error: {last_error}")
    print("Returning None — caller handles the failure.")
    return None


# =============================================================================
# LAYER 3: Fallback Chains
# Primary chain: with_structured_output (fast, clean)
# Fallback chain: plain text prompt (always works, less structured)
# .with_fallbacks() wires them together — if primary throws, fallback runs
# =============================================================================

def layer3_fallbacks(company: str, role: str):
    divider("LAYER 3 - Fallback Chains (.with_fallbacks())")
    print("Primary chain: structured output (strict, may fail)")
    print("Fallback chain: plain text summary (always works)\n")

    # Primary: strict structured output
    primary_prompt = ChatPromptTemplate.from_template(
        "Return structured placement info for {role} at {company}. "
        "Must include: difficulty, rounds list, top topics, CTC range."
    )
    primary_chain = (
        primary_prompt
        | llm.with_structured_output(PrepSummary)
        | RunnableLambda(lambda p: {
            "source":     "structured",
            "company":    p.company,
            "difficulty": p.difficulty,
            "rounds":     p.rounds,
            "top_topics": p.top_topics,
            "ctc":        p.ctc_lpa,
          })
    )

    # Fallback: plain text, always returns something
    fallback_prompt = ChatPromptTemplate.from_template(
        "Briefly describe the interview process and salary for {role} at {company} in India. "
        "Keep it under 100 words."
    )
    fallback_chain = (
        fallback_prompt
        | llm
        | StrOutputParser()
        | RunnableLambda(lambda text: {
            "source":  "fallback (plain text)",
            "content": text,
          })
    )

    # Wire primary → fallback
    robust_chain = primary_chain.with_fallbacks([fallback_chain])

    result = robust_chain.invoke({"company": company, "role": role})

    print(f"Chain used  : {result.get('source')}")
    if result.get("source") == "structured":
        print(f"Difficulty  : {result['difficulty']}")
        print(f"Rounds      : {' → '.join(result['rounds'])}")
        print(f"CTC         : {result['ctc']}")
    else:
        print(f"Plain text  :\n{result.get('content')}")

    return result


# =============================================================================
# BONUS: Safe Parser Wrapper
# A reusable utility that wraps any chain in try/except and always returns
# either a valid result or a clean error dict — never raises.
# =============================================================================

def safe_invoke(chain, inputs: dict, fallback_value=None):
    """Run a chain safely. Returns result or fallback_value on any error."""
    try:
        return chain.invoke(inputs)
    except Exception as e:
        print(f"[safe_invoke caught: {type(e).__name__}: {e}]")
        return fallback_value if fallback_value is not None else {"error": str(e)}


def bonus_safe_wrapper(company: str):
    divider("BONUS - safe_invoke() Utility")
    print("Wrap any chain call in safe_invoke() to guarantee it never raises.\n")

    structured_llm = llm.with_structured_output(PrepSummary)

    # Normal call
    print("Calling with a valid company...")
    result = safe_invoke(structured_llm, f"Prep summary for {company} India fresher.",
                         fallback_value=None)
    if result:
        print(f"  Got PrepSummary: difficulty={result.difficulty}")
    else:
        print("  Got None (chain failed, but didn't crash)")

    # Simulate a bad call (empty string)
    print("\nCalling with empty input...")
    result2 = safe_invoke(structured_llm, "",
                          fallback_value={"error": "empty input"})
    print(f"  Got: {result2}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Day 13 - Robustness: Parsers, Retries, and Fallbacks")
    print("Three layers of defense against LLM failures.\n")

    company = input("Company: ").strip() or "TCS"
    role    = input("Role   : ").strip() or "SDE-1"

    # Layer 1: PydanticOutputParser
    layer1_pydantic_output_parser(company)
    time.sleep(5)

    # Layer 2: retry logic
    layer2_retry(company)
    time.sleep(5)

    # Layer 3: fallback chains
    layer3_fallbacks(company, role)
    time.sleep(5)

    # Bonus: safe_invoke
    bonus_safe_wrapper(company)

    divider("Day 13 Complete")
    print("Day 11: with_structured_output + Pydantic   (clean validated JSON)")
    print("Day 13: parsers + retry + fallback chains    (never crashes in prod)")
    print("Day 14: Week 2 Capstone - Full Research Chain (everything together)")
    print("=" * 60)
