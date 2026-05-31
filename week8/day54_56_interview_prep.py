"""
Day 54-56 — Interview Prep on What You Built
===============================================
Practice explaining every decision out loud.
These are real questions from real interviews.

Strategy: for each question, give a 2-minute answer that covers:
  1. What (what did you do)
  2. Why (why that choice, not alternatives)
  3. Trade-offs (what you gave up)

Run:
  python week8/day54_56_interview_prep.py   # prints all Q&A to practice from
"""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


INTERVIEW_QA = [
    (
        "Walk me through your agent's architecture.",
        """The app has two pages. The Chat page is the core: when a user asks a question,
it fires 3 parallel Tavily web searches — one for general interview forums, one
restricted to glassdoor.com, and one restricted to Naukri/LinkedIn job portals.
These run simultaneously using Python's ThreadPoolExecutor, so total time is
roughly the slowest single search (~2-3s) instead of 3 sequential searches (~9s).
All 3 sets of results feed into one structured Gemini prompt that returns 4 sections:
Web summary, Glassdoor summary, Jobs summary, and a full Answer. I display the first
3 as side-by-side coloured panels and the Answer as a chat bubble.
The Interview Questions page is simpler: it just calls Gemini directly for questions,
no web search, because questions are stable enough to not need real-time data."""
    ),
    (
        "How does your app handle failures?",
        """Three layers. First, each Tavily future has a 25-second timeout and a _safe()
wrapper that returns an empty list on exception — so if Glassdoor search fails,
the other two still complete and the AI still has context to work with.
Second, the _gemini() function retries once after 3 seconds on transient errors,
and returns a clear user-readable message on 429 quota errors (instead of showing
the raw exception). Third, I've structured the Gemini prompt so it explicitly asks
for all 4 sections — if one source has no data, it says 'No data found' gracefully
rather than hallucinating. In production I'd add Sentry to capture any unhandled
exceptions with full stack traces."""
    ),
    (
        "What happens when two users research the same company at the same time?",
        """Right now, nothing bad — each session is independent. st.session_state is
per-user-session, so two users researching Google simultaneously each get their own
copy. The Tavily and Gemini API calls are stateless HTTP requests that run in parallel
without interfering. The only shared resource is ChromaDB, and we're using embedded
mode (each Streamlit process has its own file lock), so there's no race condition.
If I scaled to multiple Streamlit server instances, I'd need to move ChromaDB to
server mode and use a message queue (Redis/Celery) to serialize requests. I'd also
add the persistent file cache from Day 50 so the second user gets the cached result
instead of hitting the API again."""
    ),
    (
        "Why ChromaDB instead of a SQL database?",
        """ChromaDB is a vector database — it stores embeddings and finds similar ones
using cosine similarity. For our RAG use case in Week 3, 'find the 3 most relevant
chunks about Google interview DSA questions' is a semantic query that SQL can't handle
efficiently. SQL uses exact string matching or full-text search (BM25), which would
miss synonyms and paraphrases. Cosine similarity finds chunks that are semantically
close even if they use different words. For the rest of the app — company metadata,
session data — SQL would actually be better, and I kept those in Python dicts and
st.session_state rather than forcing everything into ChromaDB."""
    ),
    (
        "How do you prevent your API costs from exploding?",
        """Three layers. First, the architecture: 3 Tavily searches + 1 Gemini call
per question, not 3 Gemini calls. Second, session-level rate limiting: the app
tracks request count and estimated token usage, warns at 80% of the daily limit,
and blocks at 100% with a friendly message. Third, caching: if a company was
researched in this session, I return the cached result from st.session_state
immediately with $0 cost. For production I'd add a 24-hour persistent file cache
so the second user asking about the same company also gets a free hit."""
    ),
    (
        "How would you add a mock interview feature?",
        """I'd add a new MockInterviewAgent that runs 5 rounds of questioning.
State would have: company, role, current_question_number, qa_history, and feedback.
The flow: QuestionGeneratorNode picks a question based on focus area →
CandidateAnswerNode (user input) → FeedbackNode (Gemini evaluates the answer
and gives specific feedback) → loop back for next question or → FinalScoreNode.
In the current architecture I'd add a new page in the Streamlit nav and a new
stream_mock_interview() generator that yields events for each question-answer pair.
The hard part is state management across multiple rounds — LangGraph's checkpointer
would handle this cleanly by saving state after each round."""
    ),
    (
        "What is a token?",
        """A token is the basic unit that language models process. Roughly 1 token ≈
4 characters or 0.75 words in English. 'Hello world' is 2 tokens. Tokens matter
for two reasons: cost (most APIs charge per 1000 tokens) and context window (models
can only see a limited number of tokens at once — Gemini 2.5 Flash has a 1M token
window, GPT-4 has 128K). Chunking exists because RAG documents are too long to fit
in one context window — you split them into ~500-token chunks, embed each chunk,
and at query time retrieve only the 3-5 most relevant chunks."""
    ),
    (
        "Explain your CI/CD pipeline.",
        """GitHub Actions runs on every push. Five jobs in order:
1. Lint (ruff) — catches style errors, runs in ~7 seconds.
2. Unit tests — 21 tests, all external APIs mocked with unittest.mock.patch,
   runs in ~17 seconds with zero API quota.
3. Integration tests — 18 tests with real LangGraph and a temp SQLite checkpointer,
   runs in ~25 seconds.
4. Docker build — proves the image actually builds end-to-end, ~90 seconds.
5. CI Summary — prints a Markdown table of all job results in the Actions UI.
Jobs 3 and 4 both need: unit-tests to pass. Job 5 needs all four.
If any job fails, Railway's deploy step never runs — no broken code reaches production."""
    ),
    (
        "How does parallel search work technically?",
        """Python's concurrent.futures.ThreadPoolExecutor. I submit 3 callables —
_search() for web, _search_domains() for Glassdoor, _search_domains() for job portals —
and get back Future objects. I call future.result(timeout=25) on each.
Because the GIL is released during I/O (HTTP requests), all 3 searches genuinely
run in parallel on separate threads. Total time is max(t_web, t_gd, t_jobs) instead
of t_web + t_gd + t_jobs. The _safe() wrapper catches any exception (network error,
timeout) and returns an empty list, so one failing source doesn't break the others."""
    ),
    (
        "What would you change if you had to scale to 10,000 users?",
        """Move from Streamlit to FastAPI + React: Streamlit runs a Python process per
user, which doesn't scale past ~50 concurrent users. With FastAPI, I'd handle requests
asynchronously and use a connection pool. Add Redis for the cache layer instead of
JSON files — atomic operations, TTL support, works across multiple server instances.
Move ChromaDB from embedded mode to server mode with a single persistent instance.
Put the 3 parallel searches + Gemini call on a Celery task queue with a Redis broker
— the HTTP request returns a task ID immediately, the result streams back via
Server-Sent Events. Add CDN caching for any static assets. Kubernetes for
horizontal pod autoscaling when load spikes."""
    ),
]


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 54-56 — Interview Prep: What You Built")
    print(f"  {len(INTERVIEW_QA)} questions to practice")
    print("=" * 62)

    print("\n  Tips for answering architecture questions")
    print("  " + "─" * 58)
    print("  1. Draw it first — nodes and edges on paper or whiteboard")
    print("  2. What → Why → Trade-offs (always mention alternatives)")
    print("  3. Numbers matter: '3 parallel searches', '21 tests', '~3s latency'")
    print("  4. Be honest about limitations: 'In production I'd add...'")
    print()

    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  {'='*58}")
        print(f"  Q{i}: {q}")
        print(f"  {'─'*58}")
        # Indent the answer
        for line in a.strip().split('\n'):
            print(f"  {line}")

    print("\n" + "=" * 62)
    print("  Practice strategy:")
    print("  Day 54: Read all answers. Understand every word.")
    print("  Day 55: Cover the answers. Say each one out loud.")
    print("  Day 56: Mock interview with a friend — use only the whiteboard.")
    print("=" * 62)
