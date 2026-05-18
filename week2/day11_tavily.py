"""Day 11 — Web Search with Tavily
TavilySearchResults added as a tool. create_react_agent + AgentExecutor run the loop.
verbose=True lets you watch Claude reason → pick tool → read result → reason again (ReAct).
Task: research Infosys SDE-1 interview process — log every tool call."""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatAnthropic(
    model="claude-sonnet-4-5",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.2,
    max_tokens=1000,
)

# ── tool: tavily web search ─────────────────────────────────────
# max_results=3 keeps context short; k= is the same param in some versions
tavily = TavilySearchResults(
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
    max_results=3,
)
tools = [tavily]


# ── ReAct prompt ───────────────────────────────────────────────
# create_react_agent requires these exact variables in the prompt:
# {tools}  {tool_names}  {input}  {agent_scratchpad}
REACT_TEMPLATE = """You are a placement research assistant for Indian engineering students.
Answer questions using the tools available. Think step by step.

Tools available:
{tools}

Use this format:
Question: the question to answer
Thought: what you need to do next
Action: the tool to use — must be one of [{tool_names}]
Action Input: the exact query to pass to the tool
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have enough information
Final Answer: your complete answer

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

react_prompt = PromptTemplate.from_template(REACT_TEMPLATE)


# ── agent setup ────────────────────────────────────────────────
agent          = create_react_agent(llm, tools, react_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,               # prints every Thought / Action / Observation
    max_iterations=5,           # stop after 5 tool calls at most
    handle_parsing_errors=True, # retry if Claude returns malformed action
)


# ── run a research query ───────────────────────────────────────
def research(query: str) -> str:
    divider(f"Query: {query}")
    result = agent_executor.invoke({"input": query})
    return result["output"]


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 11 — Web Search with Tavily  (verbose=True)")
    print("Watch the ReAct loop: Thought → Action → Observation → repeat\n")

    # task from the plan
    answer = research("Research Infosys SDE-1 interview process — rounds, topics, difficulty, salary.")
    print(f"\n{'='*60}\nFinal Answer:\n{answer}")

    # tip: paste the verbose output into Claude.ai and ask
    # "explain what this agent is doing at each step"
