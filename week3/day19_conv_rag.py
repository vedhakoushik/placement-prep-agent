"""Day 19 — Conversational RAG
Problem : "What about their CEO?" — retriever doesn't know what 'their' means.
Solution: create_history_aware_retriever rewrites the question using chat history
          before retrieval, so pronouns + references resolve correctly.
Task    : 6-turn conversation over Flipkart data. Every turn uses pronouns/references.
          Verify retrieval stays accurate throughout."""

import os, httpx
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH   = "week3/chroma_flipkart"   # reuse day18's persisted DB — no re-embedding

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── embeddings (same as day18) ─────────────────────────────────
class GeminiEmbeddings(Embeddings):
    def _call(self, text: str, task: str) -> list[float]:
        r = httpx.post(EMBED_URL, json={
            "model":    "models/gemini-embedding-001",
            "content":  {"parts": [{"text": text}]},
            "taskType": task,
        }, timeout=30)
        r.raise_for_status()
        return r.json()["embedding"]["values"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._call(t, "RETRIEVAL_DOCUMENT") for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._call(text, "RETRIEVAL_QUERY")


embeddings = GeminiEmbeddings()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.1,
    max_output_tokens=600,
)


# ── load existing vectorstore ──────────────────────────────────
def load_vectorstore():
    if not os.path.exists(DB_PATH):
        print("ERROR: Run day18_rag.py first to build the Flipkart ChromaDB.")
        exit(1)

    vs = Chroma(
        persist_directory = DB_PATH,
        embedding_function= embeddings,
        collection_name   = "flipkart",
    )
    print(f"  Loaded ChromaDB: {vs._collection.count()} chunks (no re-embedding)")
    return vs


# ── build conversational RAG chain ────────────────────────────
def build_conv_chain(vectorstore):
    divider("Building Conversational RAG Chain")

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # Step 1: history-aware retriever
    # This prompt tells the LLM to rewrite the user's question into a
    # standalone question that makes sense WITHOUT the conversation history.
    # "What about their CEO?" + history → "Who is Flipkart's CEO?"
    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Given the chat history and the latest user question, "
         "rewrite the question as a standalone question that can be understood "
         "without the chat history. Do NOT answer — only rewrite. "
         "If the question is already standalone, return it as-is."),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # create_history_aware_retriever: rewrites question → retrieves chunks
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_prompt
    )

    # Step 2: answer chain — given context + history → answer
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a placement research assistant. Answer using ONLY the context below. "
         "Keep answers concise (3-5 sentences). If the answer isn't in the context, say so.\n\n"
         "Context:\n{context}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    qa_chain  = create_stuff_documents_chain(llm, qa_prompt)

    # Final chain: history-aware retriever + QA chain
    rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

    print("  ✓ create_history_aware_retriever — rewrites pronouns before retrieval")
    print("  ✓ create_retrieval_chain         — retrieves + answers with history")
    return rag_chain


# ── 6-turn conversation ────────────────────────────────────────
# Each turn uses a pronoun or reference — retriever must resolve them correctly
TURNS = [
    "Tell me about Flipkart's founding.",                        # Turn 1: baseline
    "Who exactly were the founders?",                            # Turn 2: "the founders" = Flipkart's
    "Which company acquired them and when?",                     # Turn 3: "them" = Flipkart
    "How much did they pay for the acquisition?",                # Turn 4: "they" = the acquirer
    "What logistics service does the company operate?",          # Turn 5: "the company" = Flipkart
    "Is that service still active today?",                       # Turn 6: "that service" from turn 5
]

def run_conversation(chain):
    divider("6-Turn Conversation (pronouns + references across turns)")

    chat_history = []   # grows each turn — passed to chain every time

    for i, question in enumerate(TURNS, 1):
        print(f"\n  Turn {i} — Q: {question}")

        result = chain.invoke({
            "input":        question,
            "chat_history": chat_history,
        })

        answer  = result["answer"]
        context = result.get("context", [])

        print(f"           A: {answer[:300]}...")

        # show which URLs backed this answer
        urls = list({d.metadata.get("source", "?") for d in context})
        print(f"           Sources: {', '.join(urls)}")

        # append to history so next turn has full context
        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=answer))

    print(f"\n  History length at end: {len(chat_history)} messages ({len(TURNS)} turns)")


# ── show why it matters ────────────────────────────────────────
def explain_the_problem():
    divider("Why history-aware retrieval matters")
    print("""
  WITHOUT create_history_aware_retriever:
    Turn 3 query sent to ChromaDB: "Which company acquired them and when?"
    ChromaDB searches for "them" — finds nothing useful.
    Answer is wrong or empty.

  WITH create_history_aware_retriever:
    LLM rewrites: "Which company acquired them?" → "Which company acquired Flipkart?"
    ChromaDB searches for "Flipkart acquisition" — finds Walmart chunk.
    Answer is correct and grounded.

  The rewrite happens BEFORE retrieval — the LLM reads history and fills in pronouns.
""")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 19 — Conversational RAG")
    print("  Reuses Day 18's Flipkart ChromaDB — no re-embedding needed.\n")

    explain_the_problem()

    vectorstore = load_vectorstore()
    chain       = build_conv_chain(vectorstore)
    run_conversation(chain)

    divider("Key takeaway")
    print("  create_history_aware_retriever = the fix for pronoun/reference problems.")
    print("  It rewrites every question into standalone form before hitting ChromaDB.")
    print("  Day 20-21: build the full Company Intelligence Store mini-project.")
