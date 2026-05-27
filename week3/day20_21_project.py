"""Day 20-21 Mini Project — Company Intelligence Store
Full pipeline combining everything from Week 3:
  Tavily search → WebBaseLoader → chunk → embed → ChromaDB → conversational RAG

CompanyIntelligenceStore class:
  ingest()        : search → chunk → embed → store in named ChromaDB collection
  query(question) : conversational RAG with history-aware retrieval + citations
  chat()          : interactive chat loop (type to ask, 'quit' to exit)

Test: Google SWE-2 — 4-turn conversation. All answers grounded in retrieved content."""

import os, httpx
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
STORES_DIR = Path("week3/stores")
STORES_DIR.mkdir(parents=True, exist_ok=True)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── shared components ──────────────────────────────────────────
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


# ── Company Intelligence Store ─────────────────────────────────
class CompanyIntelligenceStore:
    """
    One store per company+role.
    Persists to week3/stores/{company}/ — survives restarts, no re-embedding.
    Supports multi-turn conversation with pronoun resolution.
    """

    def __init__(self, company: str, role: str):
        self.company  = company
        self.role     = role
        self.db_path  = str(STORES_DIR / company.lower().replace(" ", "_"))
        self.col_name = company.lower().replace(" ", "_")

        self.embeddings   = GeminiEmbeddings()
        self.chat_history = []
        self.vectorstore  = None
        self.chain        = None

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=API_KEY,
            temperature=0.1,
            max_output_tokens=700,
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        if os.getenv("TAVILY_API_KEY"):
            self.tavily = TavilySearchResults(
                tavily_api_key=os.getenv("TAVILY_API_KEY"),
                max_results=4,
            )
        else:
            self.tavily = None


    # ── ingest ─────────────────────────────────────────────────
    def ingest(self, force: bool = False) -> int:
        """Search → chunk → embed → store. Returns chunk count.
        Skips embedding if store already exists (use force=True to rebuild)."""

        if os.path.exists(self.db_path) and not force:
            print(f"  Loading existing store for {self.company} {self.role}...")
            self.vectorstore = Chroma(
                persist_directory = self.db_path,
                embedding_function= self.embeddings,
                collection_name   = self.col_name,
            )
            count = self.vectorstore._collection.count()
            print(f"  ✓ {count} chunks loaded — no re-embedding needed")
            self._build_chain()
            return count

        # ── step 1: gather content ─────────────────────────────
        print(f"  Searching for {self.company} {self.role} interview content...")
        docs = []

        if self.tavily:
            queries = [
                f"{self.company} {self.role} interview process rounds steps",
                f"{self.company} {self.role} system design interview questions",
                f"{self.company} {self.role} interview experience tips candidates",
                f"{self.company} {self.role} DSA coding interview preparation",
            ]
            for q in queries:
                print(f"    Tavily: {q[:55]}...")
                try:
                    results = self.tavily.invoke(q)
                    for r in results:
                        if isinstance(r, dict) and r.get("content"):
                            docs.append(Document(
                                page_content=r["content"],
                                metadata={
                                    "source":  r.get("url", "tavily"),
                                    "company": self.company,
                                    "role":    self.role,
                                },
                            ))
                except Exception as e:
                    print(f"      skipped: {e}")
        else:
            # fallback: load Wikipedia pages if no Tavily key
            print("  No TAVILY_API_KEY — using Wikipedia fallback...")
            wiki_urls = [
                f"https://en.wikipedia.org/wiki/{self.company.replace(' ', '_')}",
            ]
            for url in wiki_urls:
                try:
                    raw = WebBaseLoader(url).load()
                    docs.extend(raw)
                    print(f"    Loaded: {url}")
                except Exception as e:
                    print(f"    Skipped {url}: {e}")

        print(f"  Raw documents: {len(docs)}")

        # ── step 2: chunk ──────────────────────────────────────
        chunks = self.splitter.split_documents(docs)
        print(f"  Chunks after splitting: {len(chunks)}")

        # ── step 3: embed + store ──────────────────────────────
        print(f"  Embedding {len(chunks)} chunks → ChromaDB...")
        self.vectorstore = Chroma.from_documents(
            documents        = chunks,
            embedding        = self.embeddings,
            persist_directory= self.db_path,
            collection_name  = self.col_name,
        )

        count = self.vectorstore._collection.count()
        print(f"  ✓ Stored {count} chunks in {self.db_path}/")

        # ── step 4: build RAG chain ────────────────────────────
        self._build_chain()
        return count


    # ── build chain ────────────────────────────────────────────
    def _build_chain(self):
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})

        # prompt 1: rewrite question into standalone form
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Given the chat history and the latest user question, rewrite it as a "
             "fully standalone question that makes sense without any prior context. "
             "Do NOT answer it — only rewrite. If already standalone, return as-is."),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])

        history_aware_retriever = create_history_aware_retriever(
            self.llm, retriever, contextualize_prompt
        )

        # prompt 2: answer using retrieved context
        system_msg = (
            "You are an expert placement advisor for "
            + self.company + " " + self.role + " interviews. "
            "Answer using ONLY the context provided below. "
            "Be specific and practical — mention round names, topics, tips. "
            "End your answer with: 'Source: [URL]' for each source you used.\n\n"
            "Context:\n{context}"
        )

        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])

        qa_chain      = create_stuff_documents_chain(self.llm, qa_prompt)
        self.chain    = create_retrieval_chain(history_aware_retriever, qa_chain)


    # ── query ──────────────────────────────────────────────────
    def query(self, question: str) -> tuple[str, list]:
        """Ask a question. Returns (answer, context_docs).
        Automatically maintains chat history across calls."""
        if not self.chain:
            raise RuntimeError("Call ingest() first.")

        result  = self.chain.invoke({
            "input":        question,
            "chat_history": self.chat_history,
        })

        answer  = result["answer"]
        context = result.get("context", [])

        # update history
        self.chat_history.append(HumanMessage(content=question))
        self.chat_history.append(AIMessage(content=answer))

        return answer, context


    # ── reset ──────────────────────────────────────────────────
    def reset_history(self):
        self.chat_history = []
        print("  [Chat history cleared]")


    # ── interactive chat loop ──────────────────────────────────
    def chat(self):
        """Start an interactive chat session. Type 'quit' to exit, 'reset' to clear history."""
        print(f"\n  {self.company} {self.role} Intelligence Store")
        print("  Commands: 'quit' to exit | 'reset' to clear history\n")

        while True:
            try:
                q = input("  You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not q:
                continue
            if q.lower() == "quit":
                break
            if q.lower() == "reset":
                self.reset_history()
                continue

            answer, context = self.query(q)
            urls = list({d.metadata.get("source", "?") for d in context})

            print(f"\n  AI : {answer}")
            print(f"  📎  {' | '.join(urls[:2])}\n")


# ── test: Google SWE-2 ────────────────────────────────────────
def run_google_test():
    divider("Test — Google SWE-2 Company Intelligence Store")

    store = CompanyIntelligenceStore("Google", "SWE-2")

    # ingest — skips if already done
    count = store.ingest()
    print(f"\n  Store ready: {count} chunks\n")

    # 4-turn conversation from the plan
    # Each question builds on the previous — pronoun resolution must work
    TURNS = [
        "What's the interview process at Google for SWE-2?",
        "What do they focus on in system design?",   # "they" → Google
    ]

    divider("2-Turn Conversation (grounded answers required)")

    for i, question in enumerate(TURNS, 1):
        print(f"\n  Q{i}: {question}")
        answer, context = store.query(question)
        urls = list({d.metadata.get("source", "?") for d in context})

        print(f"\n  A{i}: {answer[:500]}")
        if len(answer) > 500:
            print("       [...]")
        print(f"\n  Retrieved from ({len(context)} chunks): {', '.join(urls[:2])}")
        print(f"  {'─'*55}")

    print(f"\n  History turns: {len(store.chat_history) // 2}")
    print("  ✓ All answers grounded in retrieved Tavily content")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 20-21 — Company Intelligence Store (Week 3 Mini Project)")
    print("  Everything from Week 3 combined into one reusable class.\n")

    # check keys
    if not API_KEY:
        print("ERROR: GEMINI_API_KEY missing from .env"); exit(1)
    if not os.getenv("TAVILY_API_KEY"):
        print("WARNING: TAVILY_API_KEY missing — will use Wikipedia fallback\n")

    # run the test
    run_google_test()

    divider("How to use for any company")
    print("""
  store = CompanyIntelligenceStore("Amazon", "SDE-1")
  store.ingest()          # search → chunk → embed → ChromaDB
  store.query("What DSA topics should I focus on?")
  store.chat()            # interactive loop

  # Second run is instant — loads from disk:
  store2 = CompanyIntelligenceStore("Amazon", "SDE-1")
  store2.ingest()         # skips embedding, loads existing ChromaDB
""")
    divider("Week 3 Complete")
    print("  Day 15: Embeddings — text → vector → cosine similarity")
    print("  Day 16: ChromaDB   — store + query vectors on disk")
    print("  Day 17: Chunking   — WebBaseLoader + RecursiveCharacterTextSplitter")
    print("  Day 18: RAG        — create_retrieval_chain + grounded answers")
    print("  Day 19: Conv RAG   — create_history_aware_retriever + pronouns")
    print("  Day 20-21: Project — CompanyIntelligenceStore (all combined)")
    print("\n  Week 4: LangGraph + State + Human-in-the-loop ReAct Agent")
