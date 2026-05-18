"""Day 9 — Pydantic Output Parsers
PydanticOutputParser injects format instructions directly into the prompt.
Claude reads them and returns JSON that matches the schema exactly.
Task: CompanyProfile model → parse a real company from a chain."""

import os
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_output_tokens=800,
)


# ── schema ─────────────────────────────────────────────────────
# Literal["low","medium","high"] means the field MUST be one of these three values
class CompanyProfile(BaseModel):
    company_name:     str                         = Field(description="Full company name")
    tech_stack:       list[str]                   = Field(description="Technologies the company primarily uses")
    interview_rounds: list[str]                   = Field(description="Interview stages in order")
    key_topics:       list[str]                   = Field(description="Top topics a fresher must study")
    difficulty:       Literal["low","medium","high"] = Field(description="Overall interview difficulty")


# ── parser ─────────────────────────────────────────────────────
# get_format_instructions() returns text that tells Claude exactly what JSON to return
parser = PydanticOutputParser(pydantic_object=CompanyProfile)


# ── chain ──────────────────────────────────────────────────────
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a placement advisor. Follow the output format instructions exactly."),
    ("human",  "Give me a placement profile for {company}.\n\n{format_instructions}"),
])

chain = prompt | llm | parser                   # parser validates + converts to CompanyProfile object


# ── show what format instructions look like ────────────────────
def show_format_instructions():
    divider("Format Instructions (injected into prompt)")
    print(parser.get_format_instructions())     # Claude reads this to know what JSON to return


# ── parse a company ────────────────────────────────────────────
def parse_company(company: str) -> CompanyProfile:
    divider(f"Parsing — {company}")

    profile: CompanyProfile = chain.invoke({
        "company": company,
        "format_instructions": parser.get_format_instructions(),
    })

    # result is a validated Python object — access fields with dot notation
    print(f"  Company    : {profile.company_name}")
    print(f"  Difficulty : {profile.difficulty}")          # guaranteed low/medium/high
    print(f"  Tech Stack : {', '.join(profile.tech_stack)}")
    print(f"  Rounds     : {' → '.join(profile.interview_rounds)}")
    print(f"  Key Topics : {', '.join(profile.key_topics)}")
    return profile


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    show_format_instructions()

    company = input("\nCompany to parse: ").strip() or "Infosys"
    profile = parse_company(company)

    print(f"\nObject type : {type(profile).__name__}")     # CompanyProfile — not a dict
    print(f"Pydantic validates: difficulty='{profile.difficulty}' is one of low/medium/high")
