"""
Day 52-53 — Final Polish & Portfolio Presentation
====================================================
ONE concept: the difference between a demo and a portfolio piece is
documentation, design consistency, and one compelling walkthrough video.

Checklist:
  ✓ Logo and colour theme (already set via custom CSS)
  ✓ Loading animations showing which agent is running (status boxes)
  □ "How It Works" section (add to sidebar or a Help page)
  □ 3-minute demo video (record with Loom or OBS, upload to YouTube)
  □ README: architecture diagram + demo video link
  □ CI badge in README (GitHub Actions green checkmark)
  □ Live deployment link (Railway URL)
  □ Clean folder structure with comments

README must-haves (employer checklist):
  1. What the project does (1-2 sentences)
  2. Architecture diagram (diagram.png already exists)
  3. Demo video link (YouTube unlisted)
  4. Live URL (Railway after Day 47)
  5. Local setup (pip install + .env.example + python main.py env)
  6. CI badge (already in CI/CD pipeline)
  7. Tech stack (Streamlit, LangChain, Gemini, Tavily, ChromaDB, Docker)

Demo video script (3 minutes):
  0:00  "Hi, I built a placement prep agent. Let me walk you through it."
  0:15  Show Chat page — ask a question about a real company
  0:45  Point out the 3-column source panel (Web / Glassdoor / Jobs)
  1:00  Show AI answer with source attribution
  1:15  Navigate to Interview Questions — get questions for Google SDE-2
  1:45  Show My Companies — data persists across navigation
  2:00  Open Progress page — session tracking
  2:15  "The architecture uses 3 parallel Tavily searches and one Gemini call"
  2:30  Show the Docker setup, mention Railway deployment
  2:45  "CI runs 21 unit tests and 18 integration tests on every push"
  3:00  "Questions?"

Run:
  python week8/day52_53_polish.py   # prints checklist + demo script
"""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


PORTFOLIO_CHECKLIST = [
    ("Clean README with architecture diagram",       "README.md + diagram.png"),
    ("Demo video link in README",                    "YouTube (unlisted) → README"),
    ("Live deployment URL",                          "Railway .railway.app URL"),
    ("CI badge showing green",                       ".github/workflows/ci.yml"),
    ("Docker setup documented",                      "Dockerfile + docker-compose.yml"),
    ("Local setup in < 5 commands",                  ".env.example + pip install"),
    ("Clean folder structure",                       "week1/ … week8/ + src/"),
    ("Input validation added",                       "day51_security.py patterns"),
    ("Rate limiting added",                          "day49_rate_limiting.py"),
    ("Structured logging added",                     "day48_logging.py"),
]

DEMO_SCRIPT = """
  3-minute demo video script
  ─────────────────────────────────────────────────────────────────
  0:00 — Introduction
    "I built a Placement Prep Agent — a full-stack AI app that searches
    3 real data sources simultaneously to help students prepare for
    tech company interviews. Let me show you."

  0:15 — Chat page live demo
    Open Chat. Type: "Tell me about Google SDE-2 interviews"
    Point to the 3-column panel appearing:
    "These three columns search Web, Glassdoor, and job portals in parallel
    using Tavily's API. Then one Gemini call synthesises all three into..."
    Point to the AI answer.

  1:00 — Interview Questions page
    Navigate to Questions. Enter: Google, SDE-2, DSA
    Click Get Questions.
    "This goes straight to Gemini — no web search, instant results."

  1:30 — My Companies
    Navigate to My Companies.
    "Every company I researched in Chat appears here automatically —
    including the role, summary, and research sources."

  1:50 — Architecture explanation
    Share screen on architecture diagram.
    "The backend runs 3 parallel Tavily searches using ThreadPoolExecutor,
    passes the raw results to a single structured Gemini prompt,
    and parses the response into 4 sections:
    Web summary, Glassdoor summary, Jobs summary, and full Answer."

  2:20 — CI/CD
    Show GitHub Actions green badge.
    "21 unit tests and 18 integration tests run on every push.
    All external APIs are mocked so tests run in < 30s with zero quota."

  2:40 — Docker + Railway
    "The whole stack runs in Docker — two containers: Streamlit + ChromaDB.
    Deployed to Railway with a persistent volume for the vector database."

  3:00 — Close
    "The code is on GitHub. Questions?"
"""


def check_portfolio(root: Path) -> list[tuple[str, bool]]:
    results = []
    checks = [
        ("README.md",                          root / "README.md"),
        ("diagram.png",                        root / "diagram.png"),
        ("Dockerfile",                         root / "Dockerfile"),
        ("docker-compose.yml",                 root / "docker-compose.yml"),
        (".env.example",                       root / ".env.example"),
        ("railway.toml",                       root / "railway.toml"),
        (".github/workflows/ci.yml",           root / ".github/workflows/ci.yml"),
        ("ARCHITECTURE.md",                    root / "ARCHITECTURE.md"),
        ("week6/day37_unit_tests.py",          root / "week6/day37_unit_tests.py"),
        ("week6/day38_integration_tests.py",   root / "week6/day38_integration_tests.py"),
        ("src/utils.py",                       root / "src/utils.py"),
        ("src/chroma_client.py",               root / "src/chroma_client.py"),
    ]
    for name, path in checks:
        results.append((name, path.exists()))
    return results


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 52-53 — Final Polish & Portfolio Presentation")
    print("=" * 62)

    print("\n  Portfolio checklist")
    print("  " + "─" * 58)
    for item, note in PORTFOLIO_CHECKLIST:
        print(f"  □  {item:<45} ({note})")

    print("\n  File existence check")
    print("  " + "─" * 58)
    results = check_portfolio(ROOT)
    all_present = True
    for name, exists in results:
        mark = "✓" if exists else "✗"
        print(f"  {mark}  {name}")
        if not exists:
            all_present = False

    print(DEMO_SCRIPT)

    print("\n" + "=" * 62)
    print(f"  Files in place: {'All present ✓' if all_present else 'Some missing — check above'}")
    print()
    print("  Three things that impress interviewers:")
    print("  1. Live URL that actually works")
    print("  2. Green CI badge (shows testing discipline)")
    print("  3. Architecture explanation in under 2 minutes")
    print("=" * 62)
