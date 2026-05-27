"""
Day 29 -- Multi-Agent Design (Blueprint)
=========================================
ONE concept: design the orchestrator-worker system on paper before coding it.

Same rule as Day 22 -- never code a graph you haven't drawn first.

ORCHESTRATOR-WORKER PATTERN
-----------------------------
One SupervisorAgent receives every user message.
It reads the message, decides which specialist is needed,
and delegates. It never does the work itself.

                    User message
                         |
                  [SupervisorAgent]
                  (routes the message)
                    /     |      \
           Research  Question  Feedback
           Agent     Agent     Agent
              |          |         |
           ChromaDB  ChromaDB   (no DB)
           (write)   (read)


AGENTS DEFINED
--------------
SupervisorAgent
  receives : user_message (str)
  does     : routes to one of the three agents below
  returns  : agent_called (str) + result (dict) + routing_reason (str)

ResearchAgent
  receives : company (str), role (str)
  does     : Tavily search -> Gemini synthesis -> writes to ChromaDB
  returns  : CompanyProfile (company, founded, hq, synthesis, key_topics)

QuestionAgent
  receives : company (str), role (str), focus (str)
  does     : reads ChromaDB for existing context -> Gemini generates questions
  returns  : QuestionSet (questions list, difficulty_distribution dict)

FeedbackAgent
  receives : question_text (str), user_answer (str)
  does     : Gemini evaluates the answer
  returns  : FeedbackReport (score int, strengths list, improvements list)


MESSAGE PASSING
---------------
Every agent receives a dict. Every agent returns a dict.
The supervisor puts the return dict into state["result"].

  supervisor -> ResearchAgent  : {"company": "...", "role": "..."}
  supervisor -> QuestionAgent  : {"company": "...", "role": "...", "focus": "..."}
  supervisor -> FeedbackAgent  : {"question_text": "...", "user_answer": "..."}

  ResearchAgent  -> supervisor : {"company_profile": CompanyProfile}
  QuestionAgent  -> supervisor : {"question_set": QuestionSet}
  FeedbackAgent  -> supervisor : {"feedback_report": FeedbackReport}


WHERE DOES CHROMADB LIVE?
--------------------------
Answer: SHARED. One ChromaDB instance, two collections.
  week3/qa_db  /  collection: qa_store
  ResearchAgent WRITES to it (upserts company profiles + synthesis).
  QuestionAgent READS from it (fetches relevant context before generating).
  FeedbackAgent does NOT touch it (evaluation is stateless).

Why shared?
  If ChromaDB were per-agent, QuestionAgent could not see what
  ResearchAgent stored. The whole point of the DB is cross-agent memory.


SUPERVISOR GRAPH (Day 30)
--------------------------
  START -> [route_node]
               |
      (conditional edge on routing_result)
         /         |          \
  [research_  [question_  [feedback_
   agent_node]  agent_node]  agent_node]
         \         |          /
                  END

STRUCTURED OUTPUTS (Day 31)
----------------------------
Every agent returns a Pydantic model, not a plain string.
This makes them composable -- the supervisor can inspect and validate
the result before returning it to the user.

ERROR HANDLING (Day 32)
------------------------
Every API call is wrapped with tenacity @retry.
Stop after 3 attempts. Wait: 1s -> 2s -> 4s (exponential backoff).
Every failure is logged: timestamp, node name, error message.

OBSERVABILITY (Day 33)
------------------------
LangSmith traces every node automatically.
Raw Gemini calls are wrapped with @traceable.
You can see: what the LLM received, what it returned, token count, latency.

UI (Day 34-35)
--------------
Streamlit app with 3 pages:
  Research   -- run ResearchAgent, watch nodes in real time, see profile + questions
  Chat       -- ask follow-up questions, RAG from ChromaDB
  Companies  -- comparison table of all researched companies
"""

if __name__ == "__main__":
    print("=" * 60)
    print("  Day 29 -- Multi-Agent Design")
    print("=" * 60)

    print("""
AGENT SUMMARY
-------------

SupervisorAgent
  input  : user_message (str)
  output : agent_called, routing_reason, result dict

ResearchAgent
  input  : company, role
  nodes  : search_node -> synthesize_node -> store_node
  output : CompanyProfile (Pydantic)
  writes : ChromaDB qa_store

QuestionAgent
  input  : company, role, focus
  nodes  : context_node -> generate_node
  output : QuestionSet (Pydantic)
  reads  : ChromaDB qa_store

FeedbackAgent
  input  : question_text, user_answer
  nodes  : evaluate_node
  output : FeedbackReport (Pydantic)
  db     : none

CHROMADB
  location : week3/qa_db  (shared across all agents)
  ResearchAgent writes -> QuestionAgent reads -> FeedbackAgent ignores

ROUTING EXAMPLES
  "Research Razorpay SDE-2"              -> ResearchAgent
  "10 system design questions for Meesho"-> QuestionAgent
  "I answered X. How did I do?"          -> FeedbackAgent

WEEK 5 ROADMAP
  Day 29 : Design (this file)
  Day 30 : SupervisorAgent + 3 sub-agents as LangGraphs
  Day 31 : Pydantic structured outputs + question evaluator
  Day 32 : tenacity retries + error logging
  Day 33 : LangSmith tracing
  Day 34-35 : Streamlit UI (3 pages)
""")
    print("=" * 60)
    print("  Day 29 done. Design is clear. Ready to code Day 30.")
    print("=" * 60)
