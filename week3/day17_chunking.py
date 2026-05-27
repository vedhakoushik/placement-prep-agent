"""Day 17 — Document Loading & Chunking
WebBaseLoader fetches raw text from any URL.
RecursiveCharacterTextSplitter cuts it into overlapping chunks.
chunk_size=1000  : ~150 words — enough context for one idea.
chunk_overlap=200: 20% overlap so no idea is cut off at a boundary.
Task: Load 5 pages (2 companies). Print chunk count + avg size. Show overlap."""

import os
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def divider(title=""):
    print(f"\n{'='*60}")
    if title: print(f"{title}\n{'='*60}")


# ── splitter config ────────────────────────────────────────────
# RecursiveCharacterTextSplitter tries separators in order:
# paragraph → line → sentence → word → char (never cuts mid-word if avoidable)
CHUNK_SIZE    = 1000
CHUNK_OVERLAP = 200

splitter = RecursiveCharacterTextSplitter(
    chunk_size    = CHUNK_SIZE,
    chunk_overlap = CHUNK_OVERLAP,
    separators    = ["\n\n", "\n", ". ", " ", ""],
)


# ── 5 URLs across 2 companies ──────────────────────────────────
COMPANY_URLS = {
    "Infosys": [
        "https://en.wikipedia.org/wiki/Infosys",
        "https://en.wikipedia.org/wiki/Infosys_BPM",
        "https://en.wikipedia.org/wiki/EdgeVerve_Systems",
    ],
    "TCS": [
        "https://en.wikipedia.org/wiki/Tata_Consultancy_Services",
        "https://en.wikipedia.org/wiki/TCS_iON",
    ],
}


# ── demo 1: load + chunk all pages ────────────────────────────
def demo_load_and_chunk():
    divider("Load & Chunk — 5 pages across 2 companies")

    all_chunks = []

    for company, urls in COMPANY_URLS.items():
        print(f"\n  [{company}]")
        company_chunks = []

        for url in urls:
            print(f"    Loading: {url}")
            try:
                loader = WebBaseLoader(url)
                docs   = loader.load()              # returns list of Document objects

                raw_len = len(docs[0].page_content)
                chunks  = splitter.split_documents(docs)

                # tag each chunk with source metadata
                for c in chunks:
                    c.metadata["company"] = company

                company_chunks.extend(chunks)
                print(f"      Raw chars : {raw_len:,}")
                print(f"      Chunks    : {len(chunks)}")

            except Exception as e:
                print(f"      ERROR: {e}")

        all_chunks.extend(company_chunks)
        sizes = [len(c.page_content) for c in company_chunks]
        avg   = sum(sizes) // len(sizes) if sizes else 0
        print(f"    Subtotal  : {len(company_chunks)} chunks, avg {avg} chars")

    return all_chunks


# ── demo 2: stats ──────────────────────────────────────────────
def demo_stats(chunks):
    divider("Chunk Statistics")

    sizes = [len(c.page_content) for c in chunks]
    companies = {}
    for c in chunks:
        co = c.metadata.get("company", "Unknown")
        companies[co] = companies.get(co, 0) + 1

    print(f"  Total chunks : {len(chunks)}")
    print(f"  Avg size     : {sum(sizes) // len(sizes)} chars")
    print(f"  Min / Max    : {min(sizes)} / {max(sizes)} chars")
    print(f"  chunk_size   : {CHUNK_SIZE}  chunk_overlap: {CHUNK_OVERLAP}")
    print()
    for co, count in companies.items():
        print(f"  {co:10s} : {count} chunks")


# ── demo 3: show overlap between consecutive chunks ────────────
# This is WHY overlap matters — the end of chunk N appears at the start of chunk N+1
# so an idea that spans a boundary is never lost
def demo_overlap(chunks):
    divider("Overlap Verification — consecutive chunks share content")

    # find two consecutive chunks from the same URL
    for i in range(len(chunks) - 1):
        a = chunks[i]
        b = chunks[i + 1]
        if a.metadata.get("source") == b.metadata.get("source"):
            end_of_a   = a.page_content[-CHUNK_OVERLAP:]   # last 200 chars of chunk A
            start_of_b = b.page_content[:CHUNK_OVERLAP]    # first 200 chars of chunk B

            print(f"  Source : {a.metadata.get('source','')}")
            print(f"\n  End of chunk {i} (last {CHUNK_OVERLAP} chars):")
            print(f"  ...{end_of_a!r}")
            print(f"\n  Start of chunk {i+1} (first {CHUNK_OVERLAP} chars):")
            print(f"  {start_of_b!r}...")
            print(f"\n  → These overlap — context is preserved across the boundary")
            break


# ── demo 4: pipeline function ──────────────────────────────────
# Reusable: takes URLs, returns tagged LangChain Document chunks
def load_and_chunk(urls: list[str], company: str) -> list:
    """Load a list of URLs, chunk them, tag with company name."""
    all_chunks = []
    for url in urls:
        try:
            docs   = WebBaseLoader(url).load()
            chunks = splitter.split_documents(docs)
            for c in chunks:
                c.metadata["company"] = company
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  Skipped {url}: {e}")
    return all_chunks


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    divider("Day 17 — Document Loading & Chunking")
    print("  WebBaseLoader → raw text   RecursiveCharacterTextSplitter → chunks\n")

    chunks = demo_load_and_chunk()
    demo_stats(chunks)
    demo_overlap(chunks)

    divider("Key takeaway")
    print("  Chunks are the unit of retrieval in RAG.")
    print("  chunk_overlap stops ideas from being cut in half at boundaries.")
    print("  Day 18 embeds these chunks and stores them in ChromaDB.")
