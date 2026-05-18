"""Day 8 — LangChain Setup & LCEL
# pip install langchain langchain-anthropic langchain-community langchain-core

Three primitives: ChatAnthropic | ChatPromptTemplate | JsonOutputParser
Connected with | pipe operator — same as function composition, nothing magical.
Task: recreate Day 4's company JSON extractor using LCEL instead of raw httpx."""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

# ── primitive 1: model ─────────────────────────────────────────
# same as your Week 1 httpx call — just wrapped as a LangChain Runnable
llm = ChatAnthropic(
    model="claude-sonnet-4-5",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.2,
    max_tokens=800,
)

# ── primitive 2: prompt template ───────────────────────────────
# replaces f-strings — {variable} slots filled at invoke time
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a placement advisor for Indian engineering students. "
               "Always return valid JSON when asked."),
    ("human",  "Return a JSON object for {company} with keys: "
               "company_name, hq, founded, tech_stack (list), known_for."),
])

# ── primitive 3: output parser ─────────────────────────────────
# strips markdown fences and calls json.loads() — no manual parsing needed
json_parser = JsonOutputParser()
str_parser  = StrOutputParser()     # use when you just want plain text


# ── the chain — pipe operator wires primitives together ────────
# data flows left → right: prompt fills vars → llm generates → parser cleans
json_chain = prompt | llm | json_parser
str_chain  = prompt | llm | str_parser   # same prompt, plain text output


# ── comparison: raw Week 1 vs LCEL ────────────────────────────
def show_comparison():
    divider("Week 1 Raw  vs  Week 2 LCEL")
    print("""
  Week 1 Day 4 (raw httpx):              Week 2 Day 8 (LCEL):
  ───────────────────────────────────    ──────────────────────────────────
  import httpx, json                     from langchain_anthropic import ...
  url = "https://api.anthropic.com/..."
  headers = {"x-api-key": ..., ...}      llm    = ChatAnthropic(...)
  body    = {"model":..., ...}           prompt = ChatPromptTemplate(...)
  r = httpx.post(url, json=body)         parser = JsonOutputParser()
  r.raise_for_status()
  raw  = r.json()["content"][0]["text"]  chain  = prompt | llm | parser
  data = json.loads(raw)
  return data                            result = chain.invoke({"company": c})

  ~35 lines of boilerplate               ~3 lines — identical result
""")


# ── task: company JSON extractor ───────────────────────────────
def extract_company_info(company: str) -> dict:
    divider(f"JSON extract — {company}")
    result = json_chain.invoke({"company": company})    # returns a real Python dict
    for k, v in result.items():
        print(f"  {k}: {v}")
    return result


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    show_comparison()

    company = input("Company to extract: ").strip() or "Infosys"
    data = extract_company_info(company)
    print(f"\nResult type: {type(data).__name__}")      # dict — ready to use in code
