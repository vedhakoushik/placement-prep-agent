"""Day 12 — Chains With Memory
ConversationBufferMemory  — keeps the full history (accurate, costs more tokens)
ConversationSummaryMemory — compresses history into a summary (cheaper, less precise)
RunnableWithMessageHistory — modern LCEL way, session-ID-based.
Task: ask about Amazon, then ask 'what about their competitors?' — chain must know context."""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.chains import ConversationChain

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


# ── approach 1: ConversationBufferMemory ───────────────────────
# keeps every message — accurate but grows with every turn
def demo_buffer_memory():
    divider("ConversationBufferMemory  (keeps full history)")

    memory = ConversationBufferMemory()
    chain  = ConversationChain(llm=llm, memory=memory, verbose=False)

    r1 = chain.predict(input="Tell me about Amazon as a company for a fresher.")
    print(f"Turn 1: {r1[:120]}...\n")

    r2 = chain.predict(input="What about their main competitors?")
    print(f"Turn 2: {r2[:120]}...")        # should reference Amazon without you saying it
    print(f"\n  Messages in buffer: {len(memory.chat_memory.messages)}")


# ── approach 2: ConversationSummaryMemory ──────────────────────
# Claude summarizes old history — stays small but loses fine detail
def demo_summary_memory():
    divider("ConversationSummaryMemory  (compresses history)")

    memory = ConversationSummaryMemory(llm=llm)
    chain  = ConversationChain(llm=llm, memory=memory, verbose=False)

    chain.predict(input="Tell me about Google as a company for freshers.")
    chain.predict(input="What roles do they typically hire freshers for?")
    r3 = chain.predict(input="Which role has the best salary?")
    print(f"Turn 3: {r3[:120]}...")
    print(f"\n  Summary stored:\n  {memory.buffer[:200]}...")   # compressed history


# ── approach 3: RunnableWithMessageHistory ─────────────────────
# modern LCEL approach — session_id separates different conversations
store = {}      # in-memory session store: {session_id: ChatMessageHistory}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# prompt must include MessagesPlaceholder for history to be injected
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
    """Ask a question in a named session."""
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
    ask("s1", "What about their competitors?")          # must know 'their' = Amazon

    # session 2: completely separate — no memory of session 1
    ask("s2", "What is the fresher salary at TCS?")
    ask("s2", "How does that compare to their main Indian competitors?")  # 'their' = TCS

    print(f"  Session s1 has {len(store['s1'].messages)} messages")
    print(f"  Session s2 has {len(store['s2'].messages)} messages")
    print("  Different session_id = different conversation = independent memory")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 12 — Chains With Memory")

    demo_buffer_memory()
    demo_summary_memory()
    demo_runnable_with_history()
