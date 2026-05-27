"""Day 16 — ChromaDB
Store embeddings on disk. Query by meaning, not keywords.
Uses our REST-based embedder from day15 (no gRPC issues).
Task: add 6 placement docs → query 'Java interview prep' → see what it finds."""

import os, httpx, chromadb
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH   = "week3/chroma_db"   # persisted to disk — survives restarts

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── REST embed (same as day15) ─────────────────────────────────
def embed(text: str, task: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    payload  = {
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": task,
    }
    response = httpx.post(EMBED_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]["values"]


# ── sample documents ───────────────────────────────────────────
DOCS = [
    {"id": "d1", "company": "Infosys",  "text": "Infosys uses Java, Spring Boot, Hibernate, and MySQL. Fresher CTC is 3.6 LPA."},
    {"id": "d2", "company": "Wipro",    "text": "Wipro interview: aptitude test, technical round (DSA + OOP), HR round. CTC 3.5 LPA."},
    {"id": "d3", "company": "TCS",      "text": "TCS NQT: English, quantitative aptitude, coding in Python or Java. CTC 3.36 LPA."},
    {"id": "d4", "company": "Amazon",   "text": "Amazon SDE: 2 DSA rounds + system design + bar raiser. CTC 18-30 LPA."},
    {"id": "d5", "company": "Google",   "text": "Google: 5-6 rounds, heavy DSA and system design, whiteboard coding. CTC 40+ LPA."},
    {"id": "d6", "company": "Infosys",  "text": "Infosys InfyTQ platform tests Python and database skills for freshers."},
]


# ── demo 1: create collection and add docs ─────────────────────
def demo_add():
    divider("Add Documents to ChromaDB")

    client     = chromadb.PersistentClient(path=DB_PATH)

    # delete if exists so demo is repeatable
    try:
        client.delete_collection("placement")
    except Exception:
        pass

    collection = client.create_collection("placement")

    print(f"  Embedding and storing {len(DOCS)} documents...")
    for doc in DOCS:
        vector = embed(doc["text"])
        collection.add(
            ids        =[doc["id"]],
            documents  =[doc["text"]],
            embeddings =[vector],
            metadatas  =[{"company": doc["company"]}],
        )
        print(f"    ✓ {doc['id']} — {doc['company']}: {doc['text'][:50]}...")

    print(f"\n  Collection size: {collection.count()} documents")
    print(f"  Persisted to: {DB_PATH}/")
    return collection


# ── demo 2: semantic query ─────────────────────────────────────
def demo_query(collection):
    divider("Semantic Query — find by meaning, not keywords")

    queries = [
        "Java backend interview preparation",
        "highest paying company for freshers",
        "aptitude test tips",
    ]

    for q in queries:
        print(f"\n  Query: '{q}'")
        results = collection.query(
            query_embeddings=[embed(q, task="RETRIEVAL_QUERY")],
            n_results=2,
            include=["documents", "metadatas", "distances"],
        )
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            score = 1 - dist   # ChromaDB returns distance; convert to similarity
            print(f"    #{i+1} [{meta['company']:8s}] score={score:.3f} — {doc[:70]}...")


# ── demo 3: metadata filter ────────────────────────────────────
def demo_filter(collection):
    divider("Metadata Filter — query only Infosys docs")

    q       = "technical interview preparation"
    results = collection.query(
        query_embeddings=[embed(q, task="RETRIEVAL_QUERY")],
        n_results=2,
        where={"company": "Infosys"},   # only search within Infosys docs
        include=["documents", "distances"],
    )

    print(f"  Query : '{q}'  (filtered to Infosys only)")
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        print(f"    score={1-dist:.3f} — {doc[:80]}...")


# ── demo 4: load persisted collection ─────────────────────────
def demo_persist():
    divider("Persistence — reload collection without re-embedding")

    client     = chromadb.PersistentClient(path=DB_PATH)  # same path
    collection = client.get_collection("placement")        # already there
    print(f"  Loaded '{collection.name}' — {collection.count()} docs — no API calls needed")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 16 — ChromaDB  (vector store + semantic search)")

    collection = demo_add()
    demo_query(collection)
    demo_filter(collection)
    demo_persist()

    divider("Key takeaway")
    print("  ChromaDB stores vectors on disk and retrieves by meaning.")
    print("  Day 17 wraps this into a full RAG chain: query → retrieve → LLM answer.")
