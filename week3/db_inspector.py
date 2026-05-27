"""DB Inspector — focused on Week 1 & Week 2 knowledge base.
Shows breakdown by week, file, type. Run semantic queries and see exactly
which files + chunks were matched and used as reference."""

import os, httpx, chromadb
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"

DB_PATH  = "week3/project_knowledge_db"
COL_NAME = "project_knowledge"

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

def embed_query(text: str) -> list[float]:
    r = httpx.post(EMBED_URL, json={
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]["values"]


def load_collection():
    if not os.path.exists(DB_PATH):
        print("  ERROR: Run project_rag.py first to build the Week 1 & 2 database.")
        exit(1)
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_collection(COL_NAME)


# ── overview ───────────────────────────────────────────────────
def show_overview(col):
    divider("Week 1 & 2 Knowledge Base")

    metas = col.get(include=["metadatas"])["metadatas"]
    by_week = defaultdict(set)
    for m in metas:
        by_week[m.get("week","?")].add(m.get("file","?"))

    print(f"  Total chunks : {col.count()}")
    for week in sorted(by_week.keys()):
        print(f"  {week.upper():7s}     : {len(by_week[week])} files  |  {sum(1 for m in metas if m.get('week')==week)} chunks")


# ── breakdown by file ──────────────────────────────────────────
def show_file_breakdown(col):
    divider("Files Indexed")

    metas = col.get(include=["metadatas"])["metadatas"]
    by_file = defaultdict(lambda: {"week":"","type":"","count":0})
    for m in metas:
        f = m.get("file","?")
        by_file[f]["week"]  = m.get("week","")
        by_file[f]["type"]  = m.get("type","")
        by_file[f]["count"] += 1

    cur_week = None
    for fname, info in sorted(by_file.items(), key=lambda x: (x[1]["week"], x[0])):
        if info["week"] != cur_week:
            cur_week = info["week"]
            print(f"\n  [{cur_week.upper()}]")
        print(f"    {fname:35s} {info['count']:>3} chunks")


# ── semantic query ─────────────────────────────────────────────
def run_query(col):
    divider("Semantic Query")

    q     = input("  Your question: ").strip()
    top_k = input("  Results to show [default 4]: ").strip()
    top_k = int(top_k) if top_k.isdigit() else 4

    print(f"\n  Embedding query...")
    vector  = embed_query(q)
    results = col.query(
        query_embeddings=[vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = results["documents"][0]
    metas  = results["metadatas"][0]
    dists  = results["distances"][0]

    print(f"\n  Query  : '{q}'")
    print(f"  Found  : {len(chunks)} chunks\n")

    for i, (doc, meta, dist) in enumerate(zip(chunks, metas, dists), 1):
        score = round(1 - dist, 4)
        print(f"  #{i} [{score}] {meta.get('file','')} ({meta.get('week','')})")
        print(f"     {doc[:120].strip()}...\n")

    files_used = sorted({m.get("file","?") for m in metas})
    print(f"  References: {', '.join(files_used)}")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("DB Inspector — Week 1 & 2 Knowledge Base")

    col = load_collection()
    show_overview(col)

    while True:
        print("\n  Options:")
        print("    [1] Run a semantic query")
        print("    [2] Show all files + chunk counts")
        print("    [3] Exit")

        choice = input("\n  Choice: ").strip()

        if choice == "1":
            run_query(col)
        elif choice == "2":
            show_file_breakdown(col)
        elif choice == "3":
            break
        else:
            print("  Enter 1, 2 or 3")
