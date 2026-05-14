"""
Day 8 — LangChain LCEL
Three primitives: ChatModel | PromptTemplate | OutputParser
The pipe operator chains them: prompt | model | parser
"""
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from pydantic import BaseModel, Field

load_dotenv()


# ── 1. THE MODEL ──────────────────────────────────────────────────────────────
# Same as call_gemini() in Week 1, but wrapped as a LangChain object
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=512,
)


# ── 2. PLAIN TEXT CHAIN ───────────────────────────────────────────────────────
# prompt | model | parser  — the pipe IS function composition
def plain_chain(company: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a placement advisor for Indian engineering students."),
        ("human", "In 5 bullet points, what should a fresher prepare for {company} interviews?"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"company": company})


# ── 3. JSON CHAIN (recreates Day 4's company profile) ─────────────────────────
# Pydantic model defines the exact JSON structure we want back
class CompanyProfile(BaseModel):
    company:              str       = Field(description="Company name")
    founded:              str       = Field(description="Year founded")
    hq:                   str       = Field(description="Headquarters city")
    tech_stack:           list[str] = Field(description="Main technologies used")
    known_for:            str       = Field(description="What the company is known for")
    typical_roles:        list[str] = Field(description="Common fresher roles")
    interview_difficulty: str       = Field(description="easy, medium, or hard")


def json_chain(company: str) -> dict:
    parser = JsonOutputParser(pydantic_object=CompanyProfile)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a JSON API. Return only valid JSON, no explanation."),
        ("human", "Return a company profile for {company}.\n\n{format_instructions}"),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser
    return chain.invoke({"company": company})


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, time

    company = input("Enter company name: ").strip()

    print("\n" + "="*60)
    print("PLAIN TEXT CHAIN  (prompt | model | StrOutputParser)")
    print("="*60)
    print(plain_chain(company))

    time.sleep(8)   # avoid rate limit between calls

    print("\n" + "="*60)
    print("JSON CHAIN  (prompt | model | JsonOutputParser)")
    print("="*60)
    result = json_chain(company)
    print(json.dumps(result, indent=2))

    print("\n" + "="*60)
    print("COMPARISON: Week 1 vs Week 2")
    print("="*60)
    print("Week 1: manual httpx call + json.loads() + retry loop = ~40 lines")
    print("Week 2: prompt | model | parser                        = ~5 lines")
    print("Same result. LangChain just removes the plumbing.")
