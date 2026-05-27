"""DB Manager — Full CRUD interface for the Placement Prep knowledge base.
Add, view, search, edit, and delete data just like a normal database."""

import os, httpx, chromadb, hashlib, json
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={API_KEY}"
DB_PATH   = "week3/qa_db"
COL_NAME  = "qa_store"

# ── connect ────────────────────────────────────────────────────
def connect():
    if not os.path.exists(DB_PATH):
        print("  DB not found. Run project_rag.py first."); exit(1)
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_collection(COL_NAME)

def embed(text: str, task="RETRIEVAL_QUERY") -> list[float]:
    r = httpx.post(EMBED_URL, json={
        "model":    "models/gemini-embedding-001",
        "content":  {"parts": [{"text": text}]},
        "taskType": task,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["embedding"]["values"]

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")

def pause():
    input("\n  [Press Enter to continue]")


# ── READ: list all ─────────────────────────────────────────────
def cmd_list(col):
    divider("All Records")
    data   = col.get(include=["documents","metadatas"])
    ids    = data["ids"]
    docs   = data["documents"]
    metas  = data["metadatas"]

    page_size = 10
    total     = len(ids)
    page      = 0

    while True:
        start = page * page_size
        end   = min(start + page_size, total)
        rows  = []
        for i in range(start, end):
            rows.append([
                i+1,
                ids[i][:18],
                metas[i].get("file",""),
                metas[i].get("week",""),
                metas[i].get("type",""),
                docs[i][:60].strip() + "...",
            ])

        print(f"\n  Showing {start+1}–{end} of {total} records\n")
        print(tabulate(rows, headers=["#","ID","File","Week","Type","Preview"], tablefmt="simple"))

        if end >= total:
            break
        nav = input("\n  [n] Next page  [q] Back: ").strip().lower()
        if nav == "q": break
        if nav == "n": page += 1


# ── READ: get one record ───────────────────────────────────────
def cmd_get(col):
    divider("Get Record by ID")
    data = col.get(include=["documents","metadatas"])
    ids  = data["ids"]

    print("  Available IDs (first 20):")
    for i, id_ in enumerate(ids[:20], 1):
        print(f"    [{i:>2}] {id_}")

    choice = input("\n  Enter ID or row number: ").strip()

    # resolve row number
    if choice.isdigit() and 1 <= int(choice) <= len(ids):
        rid = ids[int(choice)-1]
    else:
        rid = choice

    result = col.get(ids=[rid], include=["documents","metadatas"])
    if not result["ids"]:
        print("  Record not found."); return

    print(f"\n  ID       : {result['ids'][0]}")
    print(f"  Metadata : {json.dumps(result['metadatas'][0], indent=4)}")
    print(f"\n  Content  :\n  {result['documents'][0]}")


# ── CREATE: add a record ───────────────────────────────────────
def cmd_add(col):
    divider("Add New Record")
    print("  [1] Add Q&A     — question + answer separately")
    print("  [2] Add fact    — a single statement, no Q&A needed")
    opt = input("\n  Choice: ").strip()

    if opt == "1":
        # ── Q&A mode ──────────────────────────────────────────
        question = input("\n  Question : ").strip()
        answer   = input("  Answer   : ").strip()
        if not question or not answer:
            print("  Both fields required."); return

        company = input("  Company (optional): ").strip()
        uid     = "qa_" + hashlib.md5(question.lower().encode()).hexdigest()[:16]
        meta    = {
            "question":  question[:120],
            "source":    "manual",
            "type":      "qa",
            "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        if company: meta["company"] = company

        col.upsert(
            ids       =[uid],
            embeddings=[embed(question, "RETRIEVAL_DOCUMENT")],
            documents =[answer],
            metadatas =[meta],
        )

    elif opt == "2":
        # ── fact/statement mode ────────────────────────────────
        print("\n  Statement (type END on a new line to finish):")
        lines = []
        while True:
            line = input()
            if line.strip() == "END": break
            lines.append(line)
        statement = "\n".join(lines).strip()
        if not statement:
            print("  Nothing entered."); return

        company = input("  Company (optional): ").strip()
        uid     = "fact_" + hashlib.md5(statement.lower().encode()).hexdigest()[:16]
        meta    = {
            "question":  "",
            "source":    "manual",
            "type":      "fact",
            "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        if company: meta["company"] = company

        col.upsert(
            ids       =[uid],
            embeddings=[embed(statement, "RETRIEVAL_DOCUMENT")],
            documents =[statement],
            metadatas =[meta],
        )

    else:
        print("  Invalid choice."); return

    print(f"\n  ✓ Saved  →  Total records: {col.count()}")


# ── UPDATE: edit a record ──────────────────────────────────────
def cmd_update(col):
    divider("Update Record")

    data = col.get(include=["documents","metadatas"])
    ids  = data["ids"]

    print("  Available IDs (first 20):")
    for i, id_ in enumerate(ids[:20], 1):
        print(f"    [{i:>2}] {id_}")

    choice = input("\n  Enter ID or row number to edit: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(ids):
        rid = ids[int(choice)-1]
    else:
        rid = choice

    result = col.get(ids=[rid], include=["documents","metadatas"])
    if not result["ids"]:
        print("  Record not found."); return

    old_doc  = result["documents"][0]
    old_meta = result["metadatas"][0]

    print(f"\n  Current content:\n  {old_doc[:300]}...")
    print(f"  Current metadata: {old_meta}")
    print("\n  Enter new content (or press Enter to keep existing):")
    print("  Type END on a new line to finish:")

    lines = []
    while True:
        line = input()
        if line.strip() == "END": break
        lines.append(line)
    new_content = "\n".join(lines).strip() or old_doc

    col.upsert(
        ids       =[rid],
        embeddings=[embed(new_content, "RETRIEVAL_DOCUMENT")],
        documents =[new_content],
        metadatas =[old_meta],
    )
    print(f"  ✓ Updated ID: {rid}")


# ── DELETE: remove a record ────────────────────────────────────
def cmd_delete(col):
    divider("Delete Record(s)")
    print("  [1] Delete by ID")
    print("  [2] Delete by filter (week / type / file)")
    print("  [3] Delete ALL qa_history entries")
    opt = input("\n  Choice: ").strip()

    if opt == "1":
        rid = input("  Enter ID: ").strip()
        col.delete(ids=[rid])
        print(f"  ✓ Deleted. Total: {col.count()}")

    elif opt == "2":
        field = input("  Filter field (week / type / file / company): ").strip()
        value = input(f"  Value for '{field}': ").strip()
        result = col.get(where={field: value})
        if not result["ids"]:
            print("  No records match."); return
        print(f"  Found {len(result['ids'])} records:")
        for id_ in result["ids"]:
            print(f"    {id_}")
        confirm = input(f"\n  Delete all {len(result['ids'])} records? [y/n]: ").strip().lower()
        if confirm == "y":
            col.delete(ids=result["ids"])
            print(f"  ✓ Deleted {len(result['ids'])} records. Total: {col.count()}")

    elif opt == "3":
        result = col.get(where={"type": "qa"})
        if not result["ids"]:
            print("  No qa_history entries found."); return
        col.delete(ids=result["ids"])
        print(f"  ✓ Deleted {len(result['ids'])} qa entries. Total: {col.count()}")


# ── SEARCH: semantic query ─────────────────────────────────────
def cmd_search(col):
    divider("Semantic Search")
    q     = input("  Query: ").strip()
    top_k = input("  Top K results [default 5]: ").strip()
    top_k = int(top_k) if top_k.isdigit() else 5

    results = col.query(
        query_embeddings=[embed(q)],
        n_results=top_k,
        include=["documents","metadatas","distances"],
    )

    chunks = results["documents"][0]
    metas  = results["metadatas"][0]
    dists  = results["distances"][0]

    rows = []
    for i, (doc, meta, dist) in enumerate(zip(chunks, metas, dists), 1):
        rows.append([
            i,
            round(1-dist, 4),
            meta.get("file",""),
            meta.get("week",""),
            meta.get("type",""),
            doc[:70].strip()+"...",
        ])

    print(f"\n  Query: '{q}'  |  Found: {len(chunks)} results\n")
    print(tabulate(rows, headers=["#","Score","File","Week","Type","Preview"], tablefmt="simple"))


# ── STATS ──────────────────────────────────────────────────────
def cmd_stats(col):
    divider("Database Stats")
    metas = col.get(include=["metadatas"])["metadatas"]
    total = col.count()

    by_week = {}
    by_type = {}
    by_file = {}

    for m in metas:
        w = m.get("week","?");  by_week[w] = by_week.get(w,0) + 1
        t = m.get("type","?");  by_type[t] = by_type.get(t,0) + 1
        f = m.get("file","?");  by_file[f] = by_file.get(f,0) + 1

    print(f"  Total chunks : {total}\n")
    print("  By Week:")
    for k,v in sorted(by_week.items()): print(f"    {k:15s}: {v}")
    print("\n  By Type:")
    for k,v in sorted(by_type.items()): print(f"    {k:15s}: {v}")
    print("\n  By File (top 10):")
    for k,v in sorted(by_file.items(), key=lambda x:-x[1])[:10]:
        print(f"    {k:35s}: {v}")


# ── MAIN MENU ──────────────────────────────────────────────────
MENU = {
    "1": ("List all records",        cmd_list),
    "2": ("Get a single record",     cmd_get),
    "3": ("Add a new record",        cmd_add),
    "4": ("Update a record",         cmd_update),
    "5": ("Delete record(s)",        cmd_delete),
    "6": ("Semantic search",         cmd_search),
    "7": ("Database stats",          cmd_stats),
    "q": ("Quit",                    None),
}

if __name__ == "__main__":
    # tabulate may need installing
    try:
        from tabulate import tabulate
    except ImportError:
        os.system("pip install tabulate -q")
        from tabulate import tabulate

    col = connect()
    divider("Placement Prep — DB Manager")
    print(f"  Connected to: {DB_PATH}")
    print(f"  Collection  : {COL_NAME}  |  Records: {col.count()}")

    while True:
        divider("Menu")
        for key, (label, _) in MENU.items():
            print(f"  [{key}] {label}")

        choice = input("\n  Command: ").strip().lower()
        if choice == "q": break
        if choice in MENU and MENU[choice][1]:
            MENU[choice][1](col)
        else:
            print("  Invalid choice.")
