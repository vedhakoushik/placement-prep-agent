"""Day 18 — Full RAG Pipeline
Load → Chunk → Embed → Store in ChromaDB → Query → Retrieve → LLM → Answer
Uses create_retrieval_chain with a custom Gemini embeddings class.
Task: Load Flipkart Wikipedia. Ask 5 questions. Every answer cites source URL + chunk number."""

import os, httpx, chromadb
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH   = "week3/chroma_flipkart"

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── custom embeddings class (wraps REST API for LangChain) ─────
# LangChain's Chroma wrapper needs an Embeddings-compatible object.
# We subclass Embeddings so our REST-based embedder plugs in cleanly.
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


# ── LLM ───────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.1,
    max_output_tokens=800,
)

embeddings = GeminiEmbeddings()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ── phase 1: ingest ────────────────────────────────────────────
FLIPKART_URLS = [
    "https://en.wikipedia.org/wiki/Flipkart",
    "https://en.wikipedia.org/wiki/PhonePe",    # Flipkart's fintech spin-off
]

def ingest():
    divider("Phase 1 — Load → Chunk → Embed → Store")

    # skip re-embedding if DB already exists — saves time and API quota
    if os.path.exists(DB_PATH):
        print("  Found existing ChromaDB — loading from disk (no re-embedding)...")
        vectorstore = Chroma(
            persist_directory = DB_PATH,
            embedding_function= embeddings,
            collection_name   = "flipkart",
        )
        print(f"  ✓ Loaded {vectorstore._collection.count()} chunks from {DB_PATH}/")
        return vectorstore

    all_chunks = []
    for url in FLIPKART_URLS:
        print(f"  Loading: {url}")
        try:
            docs   = WebBaseLoader(url).load()
            chunks = splitter.split_documents(docs)
            all_chunks.extend(chunks)
            print(f"    → {len(chunks)} chunks from {len(docs[0].page_content):,} chars")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n  Total chunks to embed: {len(all_chunks)}")
    print(f"  Embedding + storing in ChromaDB...")

    vectorstore = Chroma.from_documents(
        documents        = all_chunks,
        embedding        = embeddings,
        persist_directory= DB_PATH,
        collection_name  = "flipkart",
    )

    print(f"  ✓ Stored {vectorstore._collection.count()} chunks in {DB_PATH}/")
    return vectorstore


# ── phase 2: build retrieval chain ────────────────────────────
# create_retrieval_chain = retriever + combine_docs_chain
# retriever  : finds top-k relevant chunks from ChromaDB
# stuff_chain: stuffs chunks into prompt context → LLM → answer
def build_chain(vectorstore):
    divider("Phase 2 — Build RAG Chain (create_retrieval_chain)")

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # prompt tells LLM to use ONLY the context and always cite sources
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a placement research assistant. Answer ONLY using the provided context. "
         "Do NOT use prior knowledge. If the context doesn't contain the answer, say so.\n\n"
         "After your answer, always add a 'Sources:' section listing the URL and a short "
         "quote from each chunk you used.\n\n"
         "Context:\n{context}"),
        ("human", "{input}"),
    ])

    document_chain  = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    print("  ✓ Retriever  : ChromaDB top-4 chunks")
    print("  ✓ Chain      : retrieve → stuff → Gemini → answer")
    print("  ✓ Citation   : every answer must list Sources:")
    return retrieval_chain


# ── phase 3: ask 5 questions ───────────────────────────────────
QUESTIONS = [
    "Who founded Flipkart and in what year?",
    "Which company acquired Flipkart and for how much?",
    "What is PhonePe and how is it related to Flipkart?",
    "What logistics or delivery services does Flipkart operate?",
    "What controversies or legal issues has Flipkart faced?",
]

def ask_questions(chain):
    divider("Phase 3 — 5 Questions (all answers grounded in page content)")

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n  Q{i}: {question}")
        result  = chain.invoke({"input": question})
        answer  = result["answer"]
        sources = result.get("context", [])

        print(f"\n  A{i}: {answer[:600]}...")

        # print which URLs were retrieved for this question
        urls_used = list({d.metadata.get("source", "unknown") for d in sources})
        print(f"\n  Retrieved from: {', '.join(urls_used)}")
        print(f"  {'─'*55}")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 18 — Full RAG Pipeline")
    print("  Load → Chunk → Embed → Store → Retrieve → LLM → Grounded Answer\n")

    vectorstore = ingest()
    chain       = build_chain(vectorstore)
    ask_questions(chain)

    divider("Key takeaway")
    print("  RAG = retrieval-augmented generation.")
    print("  LLM never uses prior knowledge — every answer is grounded in chunks.")
    print("  The 'Sources:' section proves which content each claim came from.")
    print("  Day 19 adds conversation memory so follow-up questions work correctly.")
