"""
Import Week 1 & 2 data into the portal's qa_db.

Sources:
  1. project_knowledge_db (already built by project_rag.py) — copies 90 records
     directly using stored embeddings (no API calls).
  2. Fresh read of week1/*.py and week2/*.py for any files not yet indexed.
  3. week2/profiles/*.json company profiles as structured facts.

Run:
    python week3/import_weeks.py
"""

import os, hashlib, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import chromadb

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────
SRC_DB   = "week3/project_knowledge_db"
SRC_COL  = "project_knowledge"
DST_DB   = "week3/qa_db"
DST_COL  = "qa_store"

STAMP = datetime.now().strftime("%Y-%m-%d %H:%M")

def divider(msg):
    print(f"\n{'-'*60}")
    print(f"  {msg}")
    print(f"{'-'*60}")


# ── Connect ────────────────────────────────────────────────────────
def open_src():
    if not Path(SRC_DB).exists():
        print(f"  ✗ Source DB not found: {SRC_DB}")
        print("    Run  python week3/project_rag.py  first.")
        return None
    client = chromadb.PersistentClient(path=SRC_DB)
    try:
        return client.get_collection(SRC_COL)
    except Exception:
        print(f"  ✗ Collection '{SRC_COL}' not found in {SRC_DB}")
        return None

def open_dst():
    Path(DST_DB).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=DST_DB)
    try:    return client.get_collection(DST_COL)
    except: return client.create_collection(DST_COL)


# ── Metadata mapping ───────────────────────────────────────────────
TYPE_MAP = {
    "python":  "fact",
    "profile": "fact",
    "qa":      "qa",
    "web":     "research",
}

def remap_meta(m: dict) -> dict:
    """Convert project_knowledge metadata → portal qa_store metadata."""
    raw_type = m.get("type", "python")
    new_type  = TYPE_MAP.get(raw_type, "fact")

    week = m.get("week", "")
    file = m.get("file", "")
    source = f"{week}/{file}" if week else file or "week_import"

    company = m.get("company", "")

    # Build a 'question' field for searchability
    if new_type == "qa":
        question = m.get("question", "")[:120]
    elif raw_type == "profile":
        question = f"Company profile: {company}" if company else "Company profile"
    else:
        question = f"Code reference: {file}" if file else ""

    return {
        "question":  question[:120],
        "source":    source,
        "type":      new_type,
        "company":   company,
        "timestamp": STAMP,
    }


# ── Step 1: Copy from project_knowledge_db ─────────────────────────
def migrate_from_project_db(src, dst):
    divider("Step 1 — Copying from project_knowledge_db")

    data = src.get(
        include=["documents", "metadatas", "embeddings"]
    )
    ids   = data["ids"]
    docs  = data["documents"]
    metas = data["metadatas"]
    embs  = data["embeddings"]

    if not ids:
        print("  Source DB is empty — nothing to copy.")
        return 0

    print(f"  Found {len(ids)} records in source DB")

    # Batch upsert in chunks of 50
    batch_size = 50
    copied = 0
    skipped = 0

    for start in range(0, len(ids), batch_size):
        end   = min(start + batch_size, len(ids))
        b_ids  = []
        b_docs = []
        b_meta = []
        b_embs = []

        for i in range(start, end):
            raw_id  = ids[i]
            doc     = docs[i]
            meta    = metas[i]
            emb     = embs[i]

            if not doc or not doc.strip():
                skipped += 1
                continue

            # Prefix id to avoid collision with qa_ / fact_ ids
            new_id = "wk_" + hashlib.md5((raw_id + doc[:40]).encode()).hexdigest()[:20]

            b_ids.append(new_id)
            b_docs.append(doc)
            b_meta.append(remap_meta(meta))
            b_embs.append(emb)

        if b_ids:
            dst.upsert(ids=b_ids, documents=b_docs, metadatas=b_meta, embeddings=b_embs)
            copied += len(b_ids)
            print(f"  OK Batch {start//batch_size + 1}: upserted {len(b_ids)} records")

    print(f"\n  Copied: {copied}  |  Skipped empty: {skipped}")
    return copied


# ── Step 2: Add company profiles as rich facts ─────────────────────
def import_profiles(dst):
    divider("Step 2 — Importing company profiles")
    profiles_dir = Path("week2/profiles")
    if not profiles_dir.exists():
        print("  No week2/profiles/ directory found — skipping.")
        return 0

    # We need embeddings for these — check if we can import the embed fn
    try:
        import httpx
        api_key = os.getenv("GEMINI_API_KEY","")
        embed_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"

        def embed(text):
            r = httpx.post(embed_url, json={
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_DOCUMENT",
            }, timeout=30)
            r.raise_for_status()
            return r.json()["embedding"]["values"]

        count = 0
        for f in sorted(profiles_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                company = d.get("company_name","")
                # Build a rich text summary of the profile
                summary = (
                    f"Company: {company}\n"
                    f"Role: {d.get('role','Software Engineer')}\n"
                    f"Difficulty: {d.get('difficulty','Medium')}\n"
                    f"Fresher CTC: {d.get('fresher_ctc','')}\n"
                    f"Interview Rounds: {' → '.join(d.get('interview_rounds',[]))}\n"
                    f"Key Topics: {', '.join(d.get('key_topics',[]))}\n"
                    f"Tech Stack: {', '.join(d.get('tech_stack',[]))}\n"
                )
                if d.get("recent_news"):
                    summary += f"Recent News: {d['recent_news']}\n"
                if d.get("interview_questions"):
                    summary += "Sample Questions:\n" + "\n".join(f"- {q}" for q in d["interview_questions"])

                uid = "prof_" + hashlib.md5(company.lower().encode()).hexdigest()[:16]
                meta = {
                    "question":  f"Company profile: {company}",
                    "source":    f"week2/profiles/{f.name}",
                    "type":      "fact",
                    "company":   company,
                    "timestamp": STAMP,
                }
                emb = embed(summary[:1000])
                dst.upsert(ids=[uid], embeddings=[emb], documents=[summary], metadatas=[meta])
                count += 1
                print(f"  ✓ Profile: {company}")
            except Exception as e:
                print(f"  ✗ {f.name}: {e}")

        return count

    except Exception as e:
        print(f"  Skipping profile embed (API error): {e}")
        return 0


# ── Step 3: Summary ────────────────────────────────────────────────
def print_summary(dst):
    divider("Import Complete — Database Summary")
    metas = dst.get(include=["metadatas"])["metadatas"]
    total = dst.count()
    by_type   = {}
    by_source = {}
    for m in metas:
        t = m.get("type","?");    by_type[t]   = by_type.get(t,0)+1
        s = m.get("source","?");
        # Group sources by week prefix
        prefix = s.split("/")[0] if "/" in s else s
        by_source[prefix] = by_source.get(prefix,0)+1

    print(f"  Total records now in qa_db: {total}")
    print(f"\n  By type:")
    for k,v in sorted(by_type.items()):
        bar = "█" * min(v, 40)
        print(f"    {k:12s}  {bar}  {v}")
    print(f"\n  By source prefix:")
    for k,v in sorted(by_source.items(), key=lambda x:-x[1])[:10]:
        print(f"    {k:25s}  {v}")
    print(f"\n  Open the portal → http://localhost:5001")


# ── Main ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Placement Prep -- Week 1 & 2 Data Import")
    print("="*60)

    src = open_src()
    dst = open_dst()

    before = dst.count()
    print(f"\n  Portal DB before: {before} records")

    # Step 1: copy from project_knowledge_db (uses stored embeddings)
    n1 = 0
    if src:
        n1 = migrate_from_project_db(src, dst)
    else:
        print("\n  Skipping Step 1 (project_knowledge_db not available)")

    # Step 2: import/refresh company profiles with embeddings
    n2 = import_profiles(dst)

    after = dst.count()
    print(f"\n  Records added: {after - before}")

    print_summary(dst)
