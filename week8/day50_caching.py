"""
Day 50 — Performance & Caching
=================================
ONE concept: the fastest API call is the one you never make.
Cache aggressively at two levels.

Level 1 — In-memory (session cache):
  If the user researches Google twice in the same session,
  return the cached result from st.session_state.companies.
  Cost: $0. Latency: 0ms. Already implemented!

Level 2 — Persistent (file/DB cache):
  If any user has researched Google this week, the result is stored
  in a JSON cache file. The second user gets a near-instant answer.
  Cost: $0. Latency: <1ms.

What NOT to cache:
  - Time-sensitive data (job postings go stale in days)
  - User-specific content (personalised answers)
  - Responses where freshness matters (news, live stock prices)

Cache invalidation rules for this app:
  - Research results: cache for 24 hours (job postings change)
  - Interview questions: cache for 7 days (stable content)
  - Company metadata (HQ, founding year): cache forever

functools.lru_cache:
  @lru_cache(maxsize=128)
  def expensive_function(arg):  # cached by arg value
      ...
  Limitation: only works for pure functions (no side effects, hashable args)

st.cache_data:
  @st.cache_data(ttl=3600)    # expire after 1 hour
  def fetch_something(query):
      ...
  Streamlit-specific. Persists across reruns but not across sessions.

Run:
  python week8/day50_caching.py   # demos both caching levels
"""

import io
import json
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CACHE_FILE = ROOT / ".research_cache.json"
CACHE_TTL_SECONDS = 86_400   # 24 hours


# ═══════════════════════════════════════════════════════════════
#  LEVEL 2 — Persistent JSON cache
# ═══════════════════════════════════════════════════════════════
class ResearchCache:
    """
    Simple JSON file cache for company research results.
    Key: company_name.lower()  Value: {result, cached_at_iso}
    TTL: 24 hours by default.
    """

    def __init__(self, path: Path = CACHE_FILE, ttl: int = CACHE_TTL_SECONDS):
        self._path = path
        self._ttl  = ttl
        self._data: dict = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2, default=str),
                               encoding="utf-8")

    def get(self, company: str):
        """Return cached result or None if missing/expired."""
        key  = company.lower().strip()
        entry = self._data.get(key)
        if not entry:
            return None
        age = (datetime.now(tz=timezone.utc)
               - datetime.fromisoformat(entry["cached_at"])).total_seconds()
        if age > self._ttl:
            del self._data[key]
            self._save()
            return None
        return entry["result"]

    def set(self, company: str, result: dict):
        """Store result with current timestamp."""
        key = company.lower().strip()
        self._data[key] = {
            "result":    result,
            "cached_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._save()

    def stats(self) -> dict:
        now = datetime.now(tz=timezone.utc)
        valid = sum(
            1 for e in self._data.values()
            if (now - datetime.fromisoformat(e["cached_at"])).total_seconds() < self._ttl
        )
        return {"total_entries": len(self._data), "valid_entries": valid}


# ═══════════════════════════════════════════════════════════════
#  LEVEL 1 — lru_cache demo
# ═══════════════════════════════════════════════════════════════
call_count = 0

@lru_cache(maxsize=64)
def fake_gemini_call(prompt_hash: int) -> str:
    """Simulates a slow Gemini call. lru_cache makes repeat calls free."""
    global call_count
    call_count += 1
    time.sleep(0.1)   # simulate 100ms latency
    return f"Answer for hash {prompt_hash}"


STREAMLIT_SNIPPET = '''
  # In week5/day34_35_app.py — add before _chat_process() call
  # ──────────────────────────────────────────────────────────────

  # Level 1 — already done: st.session_state.companies is the in-memory cache.
  # Before running a new search, check if we already have this company:

  if company in st.session_state.get("companies", {}):
      existing = st.session_state.companies[company]
      # return cached result immediately, no API call
      st.info(f"Loaded {company} from session cache — instant result, $0 cost.")
      _show_research_results(existing)
      return

  # Level 2 — file cache for cross-session persistence:
  from week8.day50_caching import ResearchCache
  cache = ResearchCache()
  cached = cache.get(company)
  if cached:
      st.info(f"Loaded {company} from cache (saved ~$0.02)")
      _show_research_results(cached)
      return

  # Only reaches here if truly uncached — run the real search
  result = run_full_research(company, role, focus)
  cache.set(company, result)
'''

INTERVIEW_QA = [
    ("What is cache invalidation and why is it hard?",
     "Cache invalidation means deciding when a cached value is stale and should be "
     "re-fetched. It's hard because you don't always know when the source data changed. "
     "Time-based TTL is the simplest strategy: cache for N hours, then re-fetch. "
     "Event-based (invalidate when a specific event fires) is more accurate but complex."),

    ("What is LRU cache and when should you use it?",
     "Least Recently Used: when the cache is full, evict the entry that was accessed "
     "least recently. Use it for pure functions with expensive computation and a small "
     "input space. functools.lru_cache handles this automatically with maxsize parameter."),

    ("What is the difference between in-memory and persistent cache?",
     "In-memory (st.session_state, lru_cache): fast, lost on process restart. "
     "Persistent (file, Redis, SQLite): survives restarts, shared across instances. "
     "For a solo Streamlit app: in-memory for same-session, file cache for cross-session."),

    ("When should you NOT cache?",
     "When freshness is critical (live stock prices, breaking news), when the result "
     "is user-specific (can't share between users), or when the computation is cheap "
     "enough that caching adds more complexity than it saves."),
]


def demo_lru_cache():
    print("\n  Level 1 — functools.lru_cache demo")
    print("  " + "─" * 50)

    global call_count
    call_count = 0

    prompts = ["google sde-2", "flipkart backend", "google sde-2", "microsoft pm",
               "flipkart backend", "google sde-2"]

    for p in prompts:
        t0 = time.perf_counter()
        fake_gemini_call(hash(p))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        hit = "HIT  (instant)" if ms < 5 else "MISS (real call)"
        print(f"  {hit}  '{p}'  {ms}ms")

    info = fake_gemini_call.cache_info()
    print(f"\n  Cache stats: {info.hits} hits / {info.misses} misses / {info.currsize} stored")
    print(f"  Real API calls made: {call_count} (saved {len(prompts)-call_count} calls)")


def demo_file_cache():
    print("\n  Level 2 — persistent JSON cache demo")
    print("  " + "─" * 50)

    cache = ResearchCache()

    companies = ["Google", "Flipkart", "Google"]   # Google twice
    for co in companies:
        t0 = time.perf_counter()
        cached = cache.get(co)
        if cached:
            ms = round((time.perf_counter() - t0) * 1000, 2)
            print(f"  HIT   '{co}' — {ms}ms — $0 cost")
        else:
            time.sleep(0.05)   # simulate API call
            ms = round((time.perf_counter() - t0) * 1000, 1)
            cache.set(co, {"company": co, "synthesis": f"Mock data for {co}"})
            print(f"  MISS  '{co}' — {ms}ms — API call made, result cached")

    print(f"\n  Cache file: {CACHE_FILE}")
    print(f"  Stats: {cache.stats()}")


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 50 — Performance & Caching")
    print("  Level 1: lru_cache (same-session)  |  Level 2: JSON file")
    print("=" * 62)

    demo_lru_cache()
    demo_file_cache()

    print("\n  Streamlit integration snippet")
    print("  " + "─" * 50)
    print(STREAMLIT_SNIPPET)

    print("\n  Interview Q&A")
    print("  " + "─" * 50)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")

    print("\n" + "=" * 62)
    print("  Golden rule: cache at the outermost layer first.")
    print("  If the session already has the data — use it. Don't call the API.")
    print("=" * 62)
