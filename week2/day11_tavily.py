"""Day 11 — Web Search with Tavily
TavilySearchResults added as a tool. create_tool_calling_agent + AgentExecutor run the loop.
verbose=True lets you watch Gemini pick a tool, read the result, and respond.
Task: research Infosys SDE-1 interview process — log every tool call."""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    max_output_tokens=1000,
)

# ── tool: tavily web search ────────────────────────────────────
tavily = TavilySearchResults(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=3,
)
tools = [tavily]


# ── prompt ─────────────────────────────────────────────────────
# create_tool_calling_agent requires MessagesPlaceholder("agent_scratchpad")
# this is where the agent writes its tool calls and results internally
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a placement research assistant for Indian engineering students. "
               "Use the search tool to find real, current information before answering."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),  # tool call history goes here
])


# ── agent setup ────────────────────────────────────────────────
# create_tool_calling_agent uses Gemini's native function calling (not text-based ReAct)
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,               # prints every tool call and result
    max_iterations=5,           # stop after 5 tool calls at most
    handle_parsing_errors=True,
)


# ── run a research query ───────────────────────────────────────
def research(query: str) -> str:
    divider(f"Query: {query}")
    result = agent_executor.invoke({"input": query})
    return result["output"]


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 11 — Web Search with Tavily  (verbose=True)")
    print("Watch the agent: pick tool → search → read result → answer\n")

    # task from the plan
    answer = research("Research Infosys SDE-1 interview process — rounds, topics, difficulty, salary.")
    print(f"\n{'='*60}\nFinal Answer:\n{answer}")
