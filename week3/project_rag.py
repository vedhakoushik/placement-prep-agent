"""Project RAG — Week 1 & Week 2 Knowledge Base
Indexes all week1 + week2 Python files and company profiles into ChromaDB.
Ask any question → retrieves relevant chunks → LLM gives a grounded answer.
Shows: chunk details, similarity scores, sources used for the answer."""

import os, json, httpx, chromadb
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

API_KEY    = os.getenv("GEMINI_API_KEY")
EMBED_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH    = "week3/project_knowledge_db"
COL_NAME   = "project_knowledge"
ROOT       = Path(".")

CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── embeddings ─────────────────────────────────────────────────
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
    max_output_tokens=800,
)

splitter = RecursiveCharacterTextSplitter(
    chunk_size    = CHUNK_SIZE,
    chunk_overlap = CHUNK_OVERLAP,
    separators    = ["\n\n", "\n", ". ", " ", ""],
)


# ── collect source files ───────────────────────────────────────
def collect_documents() -> list[Document]:
    docs = []

    # ── week1 Python files ─────────────────────────────────────
    week1_files = list(Path("week1").glob("*.py"))
    print(f"\n  Week 1 Python files ({len(week1_files)}):")
    for f in sorted(week1_files):
        content = f.read_text(encoding="utf-8", errors="ignore")
        docs.append(Document(
            page_content=content,
            metadata={
                "source": str(f),
                "week":   "week1",
                "type":   "python",
                "file":   f.name,
            }
        ))
        print(f"    ✓ {f.name:30s} ({len(content):>6,} chars)")

    # ── week2 Python files ─────────────────────────────────────
    week2_files = list(Path("week2").glob("*.py"))
    print(f"\n  Week 2 Python files ({len(week2_files)}):")
    for f in sorted(week2_files):
        content = f.read_text(encoding="utf-8", errors="ignore")
        docs.append(Document(
            page_content=content,
            metadata={
                "source": str(f),
                "week":   "week2",
                "type":   "python",
                "file":   f.name,
            }
        ))
        print(f"    ✓ {f.name:30s} ({len(content):>6,} chars)")

    # ── week2 company profiles (JSON) ──────────────────────────
    profile_files = list(Path("week2/profiles").glob("*.json"))
    print(f"\n  Week 2 Company Profiles ({len(profile_files)}):")
    for f in sorted(profile_files):
        data    = json.loads(f.read_text(encoding="utf-8"))
        # convert JSON to readable text so it chunks well
        content = (
            f"Company: {data.get('company_name','')}\n"
            f"Role: {data.get('role','')}\n"
            f"Difficulty: {data.get('difficulty','')}\n"
            f"CTC: {data.get('fresher_ctc','')}\n"
            f"Tech Stack: {', '.join(data.get('tech_stack', []))}\n"
            f"Interview Rounds: {' → '.join(data.get('interview_rounds', []))}\n"
            f"Key Topics: {', '.join(data.get('key_topics', []))}\n"
            f"Recent News: {data.get('recent_news','')}\n"
            f"Interview Questions:\n" +
            "\n".join(data.get("interview_questions", []))
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "source":  str(f),
                "week":    "week2",
                "type":    "profile",
                "file":    f.name,
                "company": data.get("company_name", ""),
            }
        ))
        print(f"    ✓ {f.name:30s} ({len(content):>6,} chars)")

    return docs


# ── build database ─────────────────────────────────────────────
def build_db(force: bool = False):
    divider("Building Knowledge Base from Week 1 & Week 2")

    if os.path.exists(DB_PATH) and not force:
        print("  Found existing DB — loading from disk (no re-embedding)...")
        vs    = Chroma(persist_directory=DB_PATH, embedding_function=embeddings, collection_name=COL_NAME)
        count = vs._collection.count()
        print(f"  ✓ {count} chunks loaded")
        return vs

    # collect raw documents
    raw_docs = collect_documents()

    # chunk
    print(f"\n  Chunking settings:")
    print(f"    chunk_size    = {CHUNK_SIZE} chars")
    print(f"    chunk_overlap = {CHUNK_OVERLAP} chars")
    print(f"    separators    = ['\\n\\n', '\\n', '. ', ' ', '']")

    chunks = splitter.split_documents(raw_docs)

    print(f"\n  Raw documents : {len(raw_docs)}")
    print(f"  Total chunks  : {len(chunks)}")
    avg = sum(len(c.page_content) for c in chunks) // len(chunks)
    print(f"  Avg chunk size: {avg} chars")

    # show chunk breakdown by source
    by_week = {}
    for c in chunks:
        w = c.metadata.get("week", "?")
        by_week[w] = by_week.get(w, 0) + 1
    for w, n in sorted(by_week.items()):
        print(f"    {w}: {n} chunks")

    # embed + store
    print(f"\n  Embedding {len(chunks)} chunks → ChromaDB (this may take a moment)...")
    vs = Chroma.from_documents(
        documents        = chunks,
        embedding        = embeddings,
        persist_directory= DB_PATH,
        collection_name  = COL_NAME,
    )
    print(f"  ✓ Stored {vs._collection.count()} chunks in {DB_PATH}/")
    return vs


# ── query + answer ─────────────────────────────────────────────
def query_and_answer(vs, question: str, top_k: int = 4):
    divider(f"Query: {question}")

    # ── retrieval ──────────────────────────────────────────────
    print(f"\n  Chunking details:")
    print(f"    chunk_size={CHUNK_SIZE}  overlap={CHUNK_OVERLAP}  top_k={top_k}")

    raw_client = chromadb.PersistentClient(path=DB_PATH)
    raw_col    = raw_client.get_collection(COL_NAME)

    embed_vec = embeddings.embed_query(question)
    results   = raw_col.query(
        query_embeddings=[embed_vec],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks_found = results["documents"][0]
    metas_found  = results["metadatas"][0]
    dists_found  = results["distances"][0]

    print(f"\n  Similar chunks found in DB: {len(chunks_found)}")
    print(f"  {'─'*55}")

    for i, (doc, meta, dist) in enumerate(zip(chunks_found, metas_found, dists_found), 1):
        score = round(1 - dist, 4)
        print(f"\n  #{i} score={score}  file={meta.get('file','')}  week={meta.get('week','')}  type={meta.get('type','')}")
        print(f"     {doc[:180].strip()}...")

    print(f"\n  {'─'*55}")

    # ── LLM answer ────────────────────────────────────────────
    # build context string from retrieved chunks
    context_parts = []
    for doc, meta in zip(chunks_found, metas_found):
        context_parts.append(
            f"[Source: {meta.get('file','')} | Week: {meta.get('week','')}]\n{doc}"
        )
    context_str = "\n\n---\n\n".join(context_parts)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a coding assistant for a placement prep agent project. "
         "Answer using ONLY the context provided. Be specific — mention file names, "
         "function names, and exact concepts from the code.\n\n"
         "After your answer, add:\n"
         "'References used:' — list each file and week you drew from.\n\n"
         "Context:\n{context}"),
        ("human", "{question}"),
    ])

    chain  = prompt | llm
    answer = chain.invoke({"context": context_str, "question": question}).content

    print(f"\n  LLM Answer:")
    print(f"  {'─'*55}")
    print(f"  {answer}")
    print(f"  {'─'*55}")

    # ── reference summary ──────────────────────────────────────
    sources = list({m.get("file","?") for m in metas_found})
    weeks   = list({m.get("week","?") for m in metas_found})
    print(f"\n  Used for reference:")
    print(f"    Files  : {', '.join(sorted(sources))}")
    print(f"    Weeks  : {', '.join(sorted(weeks))}")
    print(f"    Chunks : {len(chunks_found)} retrieved, top score = {round(1-dists_found[0], 4)}")


# ── interactive loop ───────────────────────────────────────────
def chat_loop(vs):
    divider("Ask Anything About Your Week 1 & Week 2 Code")
    print("  Type your question. 'quit' to exit.\n")

    while True:
        try:
            q = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() == "quit":
            break

        query_and_answer(vs, q)


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Project RAG — Week 1 & 2 Knowledge Base")

    vs = build_db()

    # sample question to show it working
    divider("Sample Query")
    query_and_answer(vs, "How does the conversation memory work in week 2?")

    # then go interactive
    chat_loop(vs)
