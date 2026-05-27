"""Placement Prep — Q&A Store
DB stores only: question, answer, source, timestamp.
Static files used as context but never written to DB.
"""

import os, httpx, chromadb, hashlib, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

API_KEY    = os.getenv("GEMINI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
EMBED_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
TAVILY_URL = "https://api.tavily.com/search"
QA_DB_PATH = "week3/qa_db"
COL_NAME   = "qa_store"
LOW_CONF   = 0.50

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=API_KEY,
    temperature=0.1,
    max_output_tokens=600,
)

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── embed ──────────────────────────────────────────────────────
def embed(text: str, task="RETRIEVAL_QUERY") -> list[float]:
    r = httpx.post(EMBED_URL, json={
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": task,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]["values"]


# ── db connect ─────────────────────────────────────────────────
def connect():
    Path(QA_DB_PATH).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=QA_DB_PATH)
    try:    return client.get_collection(COL_NAME)
    except: return client.create_collection(COL_NAME)


# ── db: save Q&A ──────────────────────────────────────────────
def db_save(col, question: str, answer: str, source: str):
    uid = "qa_" + hashlib.md5(question.lower().strip().encode()).hexdigest()[:16]
    col.upsert(
        ids       =[uid],
        embeddings=[embed(question, "RETRIEVAL_DOCUMENT")],
        documents =[answer],
        metadatas =[{
            "question":  question[:120],
            "source":    source,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }],
    )


# ── db: save plain statement ───────────────────────────────────
def db_save_fact(col, statement: str):
    """Store any statement/fact directly — embedded and searchable as-is."""
    uid = "fact_" + hashlib.md5(statement.lower().strip().encode()).hexdigest()[:16]
    col.upsert(
        ids       =[uid],
        embeddings=[embed(statement, "RETRIEVAL_DOCUMENT")],
        documents =[statement],
        metadatas =[{
            "question":  "",
            "source":    "manual",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }],
    )
    print(f"  ✓ Saved → DB now has {col.count()} entries")


# ── add command handler ────────────────────────────────────────
def cmd_add(col):
    print("\n  [1] Add Q&A  (question + answer separately)")
    print("  [2] Add fact (a single statement — no Q&A needed)")
    opt = input("  Choice: ").strip()

    if opt == "1":
        q = input("  Question : ").strip()
        a = input("  Answer   : ").strip()
        if q and a:
            db_save(col, q, a, "manual")
            print(f"  ✓ Saved → DB now has {col.count()} entries")
        else:
            print("  Both fields required.")

    elif opt == "2":
        print("  Statement (or paste multiple lines — type END to finish):")
        lines = []
        while True:
            line = input()
            if line.strip() == "END": break
            lines.append(line)
        statement = "\n".join(lines).strip()
        if statement:
            db_save_fact(col, statement)
        else:
            print("  Nothing entered.")


# ── db: search ────────────────────────────────────────────────
def db_search(col, question: str, top_k=3):
    if col.count() == 0:
        return []
    n = min(top_k, col.count())
    r = col.query(
        query_embeddings=[embed(question)],
        n_results=n,
        include=["documents","metadatas","distances"],
    )
    return [
        {"answer": d, "meta": m, "score": round(1 - dist, 4)}
        for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]


# ── static context (read-only, never stored) ───────────────────
def load_context() -> str:
    parts = []
    for pattern in ["week1/*.py", "week2/*.py"]:
        for f in sorted(Path(".").glob(pattern)):
            parts.append(f"[{f.name}]\n{f.read_text(errors='ignore')[:1200]}")
    for f in sorted(Path("week2/profiles").glob("*.json")):
        d = json.loads(f.read_text())
        parts.append(
            f"[{f.name}]\n"
            f"Company:{d.get('company_name')}  Difficulty:{d.get('difficulty')}  CTC:{d.get('fresher_ctc')}\n"
            f"Rounds: {' → '.join(d.get('interview_rounds',[]))}\n"
            f"Topics: {', '.join(d.get('key_topics',[]))}"
        )
    return "\n\n---\n\n".join(parts)


# ── tavily (used as context, only answer stored) ───────────────
def web_search(query: str) -> str:
    if not TAVILY_KEY: return ""
    try:
        r = httpx.post(TAVILY_URL, json={
            "api_key": TAVILY_KEY, "query": query, "max_results": 3
        }, timeout=20)
        r.raise_for_status()
        return "\n\n".join(i.get("content","") for i in r.json().get("results",[]))
    except:
        return ""


# ── ask ────────────────────────────────────────────────────────
def ask(col, question: str, static_ctx: str):
    divider(f"Q: {question}")

    # 1. search DB for past answers
    hits      = db_search(col, question)
    top_score = hits[0]["score"] if hits else 0

    print(f"\n  DB  →  {col.count()} Q&As stored  |  best match: {top_score}")
    for i, h in enumerate(hits, 1):
        print(f"  #{i} [{h['score']}]  {h['meta'].get('question','')} [{h['meta'].get('timestamp','')}]")

    # 2. pull web data only if DB confidence is low
    web_ctx = ""
    source  = "db+static"
    if top_score < LOW_CONF and TAVILY_KEY:
        print(f"  Score < {LOW_CONF} → fetching from web...")
        web_ctx = web_search(question)
        source  = "tavily+static"
        if web_ctx: print(f"  ✓ Web data: {len(web_ctx)} chars")

    # 3. build prompt context — only what was actually retrieved
    ctx_parts = []
    if hits:
        ctx_parts.append("PAST ANSWERS:\n" + "\n\n".join(
            f"Q: {h['meta'].get('question','')}\nA: {h['answer']}" for h in hits
        ))
    if web_ctx:
        ctx_parts.append("WEB:\n" + web_ctx[:2000])
    ctx_parts.append("REFERENCE:\n" + static_ctx[:2500])

    context = "\n\n===\n\n".join(ctx_parts)

    # 4. LLM generate answer
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Answer using ONLY the provided context. Be concise.\n\nContext:\n{context}"),
        ("human", "{question}"),
    ])
    answer = (prompt | llm).invoke({"context": context, "question": question}).content

    print(f"\n  Answer:\n  {'─'*55}")
    print(f"  {answer}")
    print(f"  {'─'*55}")

    # 5. store ONLY the question + answer in DB
    db_save(col, question, answer, source)
    print(f"  Saved → DB now has {col.count()} Q&As")


# ── main ───────────────────────────────────────────────────────
def main():
    col        = connect()
    static_ctx = load_context()

    divider("Placement Prep Q&A Store")
    print(f"  Q&As in DB : {col.count()}")
    print(f"  Tavily     : {'on' if TAVILY_KEY else 'off'}")
    print(f"  Type 'quit' to exit\n")

    while True:
        try:
            q = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q: continue
        if q.lower() == "quit": break
        ask(col, q, static_ctx)

if __name__ == "__main__":
    main()
