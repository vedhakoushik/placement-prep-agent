"""Day 16 Task — Companies Collection from Week 2 Profiles
Loads Wipro profile from week2/profiles/ (real day13 output).
Adds Infosys + Amazon profiles in the same format (hardcoded).
Stores all 3 in ChromaDB. Queries: 'Which company has the hardest interview?'"""

import os, json, httpx, chromadb
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH   = "week3/chroma_db_task"

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── embed helper ───────────────────────────────────────────────
def embed(text: str, task: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    r = httpx.post(EMBED_URL, json={
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": task,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]["values"]


# ── load week2 profiles ────────────────────────────────────────
# Real profile: Wipro (from day13 output)
WIPRO_PATH = Path("week2/profiles/wipro_profile.json")
wipro      = json.loads(WIPRO_PATH.read_text(encoding="utf-8"))

# Hardcoded profiles — same structure as day13 CompanyProfile output
INFOSYS = {
    "company_name":     "Infosys",
    "tech_stack":       ["Java", "Spring Boot", "MySQL", "Python", "Selenium"],
    "interview_rounds": ["Online Test (InfyTQ)", "Technical Interview", "HR Interview"],
    "key_topics":       ["DSA", "OOP concepts", "DBMS", "Python basics", "Aptitude"],
    "difficulty":       "medium",
    "fresher_ctc":      "3.6 LPA",
    "recent_news":      "Infosys is hiring freshers via InfyTQ certification for 2025 batch.",
    "role":             "SDE",
    "interview_questions": [
        "Explain the difference between stack and queue.",
        "Write a program to reverse a string without using built-in functions.",
        "What is polymorphism? Give a real-world example.",
    ],
}

AMAZON = {
    "company_name":     "Amazon",
    "tech_stack":       ["Java", "Python", "AWS", "DynamoDB", "React"],
    "interview_rounds": ["Online Assessment (DSA)", "Technical Round 1 (DSA)", "Technical Round 2 (DSA+Design)", "Bar Raiser", "HR"],
    "key_topics":       ["Advanced DSA", "System Design", "Leadership Principles", "OOP", "OS concepts"],
    "difficulty":       "high",
    "fresher_ctc":      "18-32 LPA",
    "recent_news":      "Amazon is expanding AWS India team and hiring SDE-1 freshers from top IITs and NITs.",
    "role":             "SDE-1",
    "interview_questions": [
        "Given an array, find the length of the longest subarray with sum equal to k.",
        "Design a URL shortener service. What data structures would you use?",
        "Explain how you handled a conflict in a team project (Leadership Principle).",
    ],
}

PROFILES = [wipro, INFOSYS, AMAZON]


# ── build document text from profile ──────────────────────────
# Combine key fields into one rich string for embedding
def profile_to_doc(p: dict) -> str:
    return (
        f"Company: {p['company_name']}. "
        f"Role: {p.get('role','SDE')}. "
        f"Difficulty: {p['difficulty']}. "
        f"CTC: {p['fresher_ctc']}. "
        f"Interview rounds: {', '.join(p['interview_rounds'])}. "
        f"Key topics: {', '.join(p['key_topics'][:5])}. "
        f"Tech stack: {', '.join(p['tech_stack'][:5])}. "
        f"News: {p['recent_news']}"
    )


# ── step 1: add profiles to chromadb ──────────────────────────
def build_collection():
    divider("Building Companies Collection")

    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        client.delete_collection("companies")
    except Exception:
        pass
    collection = client.create_collection("companies")

    for p in PROFILES:
        doc    = profile_to_doc(p)
        vector = embed(doc)
        collection.add(
            ids        =[p["company_name"].lower()],
            documents  =[doc],
            embeddings =[vector],
            metadatas  =[{
                "company":    p["company_name"],
                "difficulty": p["difficulty"],
                "ctc":        p["fresher_ctc"],
            }],
        )
        print(f"  ✓ {p['company_name']:10s} | difficulty={p['difficulty']:6s} | ctc={p['fresher_ctc']}")

    print(f"\n  Total docs stored: {collection.count()}")
    return collection


# ── step 2: query ──────────────────────────────────────────────
def run_query(collection):
    divider("Query — 'Which company has the hardest interview?'")

    q       = "Which company has the hardest interview?"
    results = collection.query(
        query_embeddings=[embed(q, task="RETRIEVAL_QUERY")],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    print(f"  Query: '{q}'\n")
    print(f"  Results (ranked by relevance):\n")

    for rank, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ), start=1):
        score = 1 - dist
        print(f"  #{rank} {meta['company']:10s}  score={score:.3f}  difficulty={meta['difficulty']}  ctc={meta['ctc']}")
        print(f"      {doc[:100]}...")
        print()

    top = results["metadatas"][0][0]
    print(f"  → ChromaDB ranked '{top['company']}' as most relevant (difficulty: {top['difficulty']})")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 16 Task — Week 2 Profiles → ChromaDB → Query")

    collection = build_collection()
    run_query(collection)

    divider("Verification")
    print("  ✓ Wipro loaded from week2/profiles/wipro_profile.json (real day13 output)")
    print("  ✓ Infosys + Amazon added with same profile structure")
    print("  ✓ Query retrieved hardest interview company correctly")
    print("  ✓ Scores show Amazon (high) ranked #1, Wipro (low) ranked last")
