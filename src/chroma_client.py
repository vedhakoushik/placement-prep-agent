"""
src/chroma_client.py — ChromaDB Client Factory
================================================
ONE concept: environment-aware client selection.

In Docker (production):
  The chromadb container runs as a separate service.
  CHROMA_HOST=chromadb is injected by docker-compose.
  → Returns HttpClient pointing at the container.

Locally (development):
  No server running, CHROMA_HOST is not set.
  → Returns PersistentClient using a local directory.

This lets ALL week3 scripts and the main app work in both
environments without changing a single line of their code:
just swap out the manual chromadb.PersistentClient(...) call
for get_chroma_client().

Usage:
    from src.chroma_client import get_chroma_client, get_collection

    client = get_chroma_client()
    col    = client.get_or_create_collection("my_collection")

    # or in one call:
    col = get_collection("qa_store")

Environment variables (set by docker-compose, not needed locally):
    CHROMA_HOST   — hostname of ChromaDB service  (e.g. "chromadb")
    CHROMA_PORT   — port of ChromaDB service      (default: 8000)

Local fallback path (when CHROMA_HOST is not set):
    <repo_root>/week3/qa_db    ← same directory used by week3 scripts
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Default local storage path — matches week3/project_rag.py and ask.py
_DEFAULT_LOCAL_PATH = str(ROOT / "week3" / "qa_db")


def get_chroma_client(local_path: str | None = None):
    """
    Return a ChromaDB client configured for the current environment.

    Docker / production:
        Reads CHROMA_HOST from env → returns HttpClient(host, port)
        No local files needed; data lives in the chromadb container volume.

    Local development:
        CHROMA_HOST not set → returns PersistentClient(path)
        Data is stored in a local directory (same as week3 scripts use).

    Args:
        local_path: Override the default local storage path.
                    Only used when CHROMA_HOST is not set.

    Returns:
        chromadb.HttpClient  — in Docker (server mode)
        chromadb.PersistentClient — locally (embedded mode)

    Example:
        from src.chroma_client import get_chroma_client
        client = get_chroma_client()
        col = client.get_or_create_collection("qa_store")
        col.add(documents=["doc1"], ids=["id1"])
    """
    import chromadb

    host = os.getenv("CHROMA_HOST")
    if host:
        # Running in Docker — connect to the chromadb container
        port = int(os.getenv("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)

    # Local dev — use embedded persistent storage
    path = local_path or _DEFAULT_LOCAL_PATH
    Path(path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=path)


def get_collection(name: str, local_path: str | None = None):
    """
    Get or create a named ChromaDB collection.

    Convenience wrapper around get_chroma_client().

    Args:
        name:       Collection name (e.g. "qa_store", "placement_docs").
        local_path: Override default local storage path.

    Returns:
        chromadb.Collection

    Example:
        from src.chroma_client import get_collection
        col = get_collection("placement_docs")
        results = col.query(query_texts=["system design interview"], n_results=3)
    """
    return get_chroma_client(local_path=local_path).get_or_create_collection(name)


# ─────────────────────────────────────────────────────────────────────
#  Quick diagnostic — run with:  python src/chroma_client.py
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    host = os.getenv("CHROMA_HOST")
    port = os.getenv("CHROMA_PORT", "8000")

    if host:
        mode = f"HTTP client  →  {host}:{port}  (Docker / production)"
    else:
        path = _DEFAULT_LOCAL_PATH
        mode = f"Persistent client  →  {path}  (local development)"

    print("=" * 58)
    print("  src/chroma_client.py — environment check")
    print("=" * 58)
    print(f"\n  Mode:  {mode}")

    try:
        client = get_chroma_client()
        cols   = client.list_collections()
        print(f"  OK     Connected to ChromaDB")
        print(f"  Collections ({len(cols)}): {[c.name for c in cols] or '(none yet)'}")
    except Exception as exc:
        print(f"  ERROR  Could not connect: {exc}")
        if host:
            print(f"\n  Tip: make sure the chromadb container is running:")
            print(f"       docker compose up chromadb")
        else:
            print(f"\n  Tip: the local path will be created automatically on first use.")

    print("\n" + "=" * 58)
    print("  Import with:  from src.chroma_client import get_chroma_client")
    print("=" * 58)
