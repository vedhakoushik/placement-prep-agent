"""Day 13 — Robustness: Parsers, Retries, and Fallbacks
Three layers: PydanticOutputParser → manual retry → fallback chains."""

import os, time
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

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── shared schema ──────────────────────────────────────────────
class PrepSummary(BaseModel):
    company:    str       = Field(description="Company name")
    difficulty: str       = Field(description="easy / medium / hard")
    rounds:     list[str] = Field(description="Interview rounds in order (2-5 items)")
    top_topics: list[str] = Field(description="Top 3 topics to study")
    ctc_lpa:    str       = Field(description="Fresher CTC range e.g. '4-6 LPA'")


# ── layer 1: pydanticoutputparser ──────────────────────────────
# difference from with_structured_output:
#   with_structured_output  → model API injects the schema automatically
#   PydanticOutputParser    → YOU inject format instructions into the prompt text
#                             useful when you need full control over what the prompt says

def layer1_pydantic_output_parser(company: str):
    divider("LAYER 1 — PydanticOutputParser  (schema in prompt)")

    parser = JsonOutputParser(pydantic_object=PrepSummary)
    instructions = parser.get_format_instructions()     # schema as text for the prompt

    print("Format instructions injected into prompt (first 300 chars):")
    print(instructions[:300] + "...\n")

    prompt = ChatPromptTemplate.from_template(
        "Give interview prep info for {company}.\n\n"
        "{format_instructions}\n\nReturn ONLY the JSON object."
    )
    chain = prompt | llm | parser                       # parser strips fences + parses

    result = chain.invoke({"company": company, "format_instructions": instructions})
    print(f"Difficulty : {result.get('difficulty')}")
    print(f"Rounds     : {result.get('rounds')}")
    print(f"Topics     : {result.get('top_topics')}")
    print(f"CTC        : {result.get('ctc_lpa')}")
    return result


# ── layer 2: retry logic ───────────────────────────────────────
# try with_structured_output, rephrase and retry on failure

def layer2_retry(company: str, max_retries: int = 3):
    divider("LAYER 2 — Retry on Failure")

    structured_llm = llm.with_structured_output(PrepSummary)

    # slightly different phrasings — each retry gets a more specific prompt
    prompts = [
        f"Provide a placement prep summary for {company} in India.",
        f"Give structured interview details for {company}: difficulty, rounds, topics, CTC.",
        f"For a fresher at {company}: interview rounds, difficulty, top 3 topics, and CTC range.",
    ]

    last_error = None
    for attempt, prompt_text in enumerate(prompts[:max_retries], 1):
        try:
            print(f"  Attempt {attempt}: {prompt_text[:60]}...")
            result: PrepSummary = structured_llm.invoke(prompt_text)
            print(f"  SUCCESS  difficulty={result.difficulty}, ctc={result.ctc_lpa}")
            return result
        except (ValidationError, Exception) as e:
            last_error = e
            print(f"  FAILED   {type(e).__name__}: {str(e)[:60]}")
            if attempt < max_retries:
                time.sleep(3)

    print(f"\n  All {max_retries} attempts failed. Returning None.")
    return None


# ── layer 3: fallback chains ───────────────────────────────────
# primary: structured output (strict, may fail)
# fallback: plain text (always works, less structured)
# .with_fallbacks() wires them — if primary throws, fallback runs automatically

def layer3_fallbacks(company: str, role: str):
    divider("LAYER 3 — Fallback Chains  (.with_fallbacks())")

    # primary chain: strict structured output
    primary_prompt = ChatPromptTemplate.from_template(
        "Return structured placement info for {role} at {company}."
    )
    primary_chain = (
        primary_prompt
        | llm.with_structured_output(PrepSummary)
        | RunnableLambda(lambda p: {
            "source": "structured",
            "difficulty": p.difficulty, "rounds": p.rounds,
            "topics": p.top_topics, "ctc": p.ctc_lpa,
        })
    )

    # fallback chain: plain text — always returns something
    fallback_prompt = ChatPromptTemplate.from_template(
        "Briefly describe interviews and salary for {role} at {company} in India. Under 80 words."
    )
    fallback_chain = (
        fallback_prompt | llm | StrOutputParser()
        | RunnableLambda(lambda text: {"source": "plain text fallback", "content": text})
    )

    # wire: if primary raises any exception, fallback runs
    robust_chain = primary_chain.with_fallbacks([fallback_chain])

    result = robust_chain.invoke({"company": company, "role": role})
    print(f"Chain used : {result.get('source')}")
    if result.get("source") == "structured":
        print(f"Difficulty : {result['difficulty']}")
        print(f"Rounds     : {' → '.join(result['rounds'])}")
        print(f"CTC        : {result['ctc']}")
    else:
        print(f"Text:\n{result.get('content')}")
    return result


# ── bonus: safe_invoke wrapper ─────────────────────────────────
# wrap any chain call so it never raises — returns fallback_value on error

def safe_invoke(chain, inputs, fallback_value=None):
    try:
        return chain.invoke(inputs)
    except Exception as e:
        print(f"[safe_invoke caught: {type(e).__name__}: {e}]")
        return fallback_value if fallback_value is not None else {"error": str(e)}


def bonus_safe_wrapper(company: str):
    divider("BONUS — safe_invoke()  (never raises, always returns)")

    structured_llm = llm.with_structured_output(PrepSummary)

    print("Valid call...")
    result = safe_invoke(structured_llm, f"Prep summary for {company} fresher India.",
                         fallback_value=None)
    if result:
        print(f"  Got PrepSummary: difficulty={result.difficulty}")
    else:
        print("  Got None (chain failed, did not crash)")

    print("\nEmpty input call...")
    result2 = safe_invoke(structured_llm, "", fallback_value={"error": "empty input"})
    print(f"  Got: {result2}")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    company = input("Company: ").strip() or "TCS"
    role    = input("Role   : ").strip() or "SDE-1"

    layer1_pydantic_output_parser(company)
    time.sleep(5)

    layer2_retry(company)
    time.sleep(5)

    layer3_fallbacks(company, role)
    time.sleep(5)

    bonus_safe_wrapper(company)
