"""Day 15 — Embeddings
Text → vector of numbers. Similar text → similar vector. That's it.
Uses REST API directly (v1) — same pattern as week1/gemini_client.py.
gemini-embedding-001 turns any string into a 768-dimension float list.
Task: embed company names + topics, compute similarity, show why RAG works."""

import os, math, httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
# v1 endpoint — gemini-embedding-001 is not available on v1beta (gRPC)
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── REST embed helpers ─────────────────────────────────────────
def embed_query(text: str) -> list[float]:
    """Embed a single query string → 768-dim float list."""
    payload  = {
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY",
    }
    response = httpx.post(EMBED_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["embedding"]["values"]

def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a list of document strings."""
    results = []
    for text in texts:
        payload  = {
            "model":    "models/gemini-embedding-001",
            "content":  {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_DOCUMENT",
        }
        response = httpx.post(EMBED_URL, json=payload, timeout=30)
        response.raise_for_status()
        results.append(response.json()["embedding"]["values"])
    return results


# ── cosine similarity ──────────────────────────────────────────
# 1.0 = identical direction, 0.0 = unrelated, measures angle between vectors
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot    = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


# ── demo 1: what does an embedding look like? ──────────────────
def demo_vector_shape():
    divider("What an embedding looks like")

    text   = "Infosys fresher interview process"
    vector = embed_query(text)

    print(f"  Text   : '{text}'")
    print(f"  Vector : [{vector[0]:.4f}, {vector[1]:.4f}, {vector[2]:.4f}, ...]")
    print(f"  Length : {len(vector)} dimensions")
    print("  → Every sentence becomes a fixed-size list of floats")


# ── demo 2: similar texts → close vectors ─────────────────────
def demo_similarity():
    divider("Similar text = high similarity score")

    base = "Wipro interview rounds for freshers"
    comparisons = [
        ("Very similar",       "Wipro fresher hiring process steps"),
        ("Same domain",        "TCS NQT exam pattern and syllabus"),
        ("Completely unrelated","How to make pasta carbonara"),
    ]

    base_vec = embed_query(base)
    print(f"  Base: '{base}'\n")

    for label, text in comparisons:
        score = cosine_similarity(base_vec, embed_query(text))
        bar   = "█" * int(score * 30)
        print(f"  [{label:20s}] {score:.3f}  {bar}")
        print(f"    '{text}'")


# ── demo 3: batch embed + similarity matrix ────────────────────
def demo_batch():
    divider("Batch embed — similarity matrix across 4 companies")

    labels = ["Infosys", "Wipro", "TCS", "Amazon"]
    docs   = [
        "Infosys uses Java, Spring Boot, and MySQL for enterprise projects.",
        "Wipro interview has 3 rounds: aptitude, technical, HR.",
        "TCS NQT tests aptitude, coding, and English skills.",
        "Amazon SDE interview focuses on DSA and system design.",
    ]

    vectors = embed_documents(docs)
    print(f"  Embedded {len(vectors)} documents, {len(vectors[0])} dims each\n")

    # header
    print(f"  {'':10}", end="")
    for lab in labels:
        print(f"  {lab:>8}", end="")
    print()

    # matrix
    for i, lab_i in enumerate(labels):
        print(f"  {lab_i:10}", end="")
        for j in range(len(labels)):
            score = cosine_similarity(vectors[i], vectors[j])
            print(f"  {score:>8.3f}", end="")
        print()

    print("\n  Diagonal = 1.000 (doc vs itself)")
    print("  Higher score = more semantically similar")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 15 — Embeddings  (text → vector → similarity)")
    print("  gemini-embedding-001 → float vector per text\n")

    demo_vector_shape()
    demo_similarity()
    demo_batch()

    divider("Key takeaway")
    print("  Embeddings let us find relevant docs by meaning, not keywords.")
    print("  Day 16 stores these vectors in ChromaDB for fast retrieval.")
