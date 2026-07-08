"""Day 12 — Chains With Memory
Buffer memory  — keeps every message (accurate, grows with turns)
Summary memory — LLM compresses old history (cheaper, less precise)
RunnableWithMessageHistory — modern LCEL way, session-ID-based.
Task: ask about Amazon, then 'what about their competitors?' — chain must keep context."""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

load_dotenv()

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    max_output_tokens=600,
)


# ── approach 1: manual buffer memory ──────────────────────────
# keep every message in a list — pass them all each turn
def demo_buffer_memory():
    divider("Buffer Memory  (keeps full history)")

    history = ChatMessageHistory()
    history.add_message(SystemMessage(content="You are a placement advisor for Indian engineering students."))

    def chat(question: str) -> str:
        history.add_user_message(question)
        response = llm.invoke(history.messages)
        history.add_ai_message(response.content)
        return response.content

    r1 = chat("Tell me about Amazon as a company for a fresher.")
    print(f"Turn 1: {r1[:120]}...\n")

    r2 = chat("What about their main competitors?")  # 'their' = Amazon from history
    print(f"Turn 2: {r2[:120]}...")
    print(f"\n  Messages in buffer: {len(history.messages)}")


# ── approach 2: manual summary memory ─────────────────────────
# after each turn, ask the LLM to compress history into one paragraph
def demo_summary_memory():
    divider("Summary Memory  (compresses history into a running summary)")

    summary = ""

    def chat(question: str) -> str:
        nonlocal summary

        # build prompt: inject summary + new question
        msgs = [SystemMessage(content="You are a placement advisor for Indian engineering students.")]
        if summary:
            msgs.append(SystemMessage(content=f"Conversation so far (summary): {summary}"))
        msgs.append(HumanMessage(content=question))

        response = llm.invoke(msgs)
        answer   = response.content

        # compress history into updated summary
        compress_prompt = (
            f"Summarise this conversation in 2-3 sentences:\n"
            f"Previous summary: {summary}\n"
            f"User: {question}\nAssistant: {answer}"
        )
        summary = llm.invoke([HumanMessage(content=compress_prompt)]).content
        return answer

    chat("Tell me about Google as a company for freshers.")
    chat("What roles do they typically hire freshers for?")
    r3 = chat("Which role has the best salary?")
    print(f"Turn 3: {r3[:120]}...")
    print(f"\n  Summary stored:\n  {summary[:200]}...")


# ── approach 3: RunnableWithMessageHistory ─────────────────────
# modern LCEL — session_id separates different conversations automatically
store = {}   # {session_id: ChatMessageHistory}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a placement advisor helping an engineering student in India."),
    MessagesPlaceholder(variable_name="history"),   # past messages injected here
    ("human", "{input}"),
])

chain = prompt | llm | StrOutputParser()

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

def ask(session_id: str, question: str) -> str:
    response = chain_with_history.invoke(
        {"input": question},
        config={"configurable": {"session_id": session_id}},
    )
    print(f"  Q: {question}")
    print(f"  A: {response[:120]}...\n")
    return response


def demo_runnable_with_history():
    divider("RunnableWithMessageHistory  (session-ID-based, modern LCEL)")

    # session 1: Amazon conversation
    ask("s1", "Tell me about Amazon's interview process for a fresher SDE.")
    ask("s1", "What about their competitors?")           # 'their' = Amazon from s1 history

    # session 2: separate — no memory of session 1
    ask("s2", "What is the fresher salary at TCS?")
    ask("s2", "How does that compare to their main Indian competitors?")  # 'their' = TCS

    print(f"  Session s1 has {len(store['s1'].messages)} messages")
    print(f"  Session s2 has {len(store['s2'].messages)} messages")
    print("  Different session_id = independent memory")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 12 — Chains With Memory")

    demo_buffer_memory()
    demo_summary_memory()
    demo_runnable_with_history()
