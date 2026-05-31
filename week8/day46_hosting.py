"""
Day 46 — Choosing Where to Host
=================================
ONE concept: every hosting platform makes different trade-offs between
cost, effort, and control. Pick the one that matches your project's needs
— not the one that sounds most impressive.

Platform comparison for a Streamlit + ChromaDB app:

Platform      | Best For                        | Cost          | Effort  | Verdict
--------------|---------------------------------|---------------|---------|--------
Hugging Face  | Quick demo, portfolio           | Free          | Lowest  | Fine for demos
Railway       | Full-stack, persistent volumes  | ~$5/mo        | Low     | ✓ Best for us
Render        | Production web apps             | Free → $7/mo  | Low     | Good alt
Fly.io        | Docker, global edge             | Free → PAYG   | Medium  | Overkill
AWS/GCP/Azure | Enterprise, full control        | PAYG          | High    | Way overkill

Why Railway for this project:
  1. Auto-detects our Dockerfile — zero extra config
  2. Persistent volumes → ChromaDB data survives redeploys
  3. Environment variables dashboard → API keys stay secure
  4. Free subdomain: placement-prep-agent.railway.app
  5. GitHub integration → push to main → auto-deploy

Key deployment concepts:
  Procfile     — tells the platform how to start your app (we use Dockerfile instead)
  Dockerfile   — already written. Railway uses it automatically
  Environment  — API keys live in the platform dashboard, NOT in code
  Volume       — persistent disk storage (needed for ChromaDB SQLite files)
  Domain       — Railway gives a free .railway.app URL; custom domains cost nothing extra

Run:
  python week8/day46_hosting.py   # prints this summary + checks readiness
"""

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent.parent


PLATFORM_TABLE = """
  Platform Comparison
  ───────────────────────────────────────────────────────────────────
  Platform       Best For                   Cost          Effort
  ───────────────────────────────────────────────────────────────────
  Hugging Face   Demos, portfolio           Free          ★☆☆☆☆
  Railway        Full-stack + volumes       ~$5/mo        ★★☆☆☆  ← we use this
  Render         Production web apps        Free → $7/mo  ★★☆☆☆
  Fly.io         Docker, global edge        Free → PAYG   ★★★☆☆
  AWS/GCP/Azure  Enterprise, full control   PAYG          ★★★★★
"""

RAILWAY_SETUP = """
  Railway deployment steps (Day 47 task)
  ───────────────────────────────────────────────────────────────────
  1. railway.app → New Project → Deploy from GitHub repo
  2. Railway detects Dockerfile automatically
  3. Add environment variables:
       GEMINI_API_KEY   = your key
       TAVILY_API_KEY   = your key
       LANGSMITH_API_KEY = your key (optional)
  4. Add a volume → mount to /app/chroma_db
  5. Deploy → get free subdomain: <your-app>.railway.app
  6. Optional: Settings → Custom Domain → point your domain
"""

INTERVIEW_QA = [
    ("Why did you choose Railway over Heroku/Vercel?",
     "Railway natively supports Docker containers and persistent volumes, which "
     "ChromaDB needs for its SQLite + HNSW index files to survive redeploys. "
     "Vercel is serverless (no persistent disk), Heroku deprecated its free tier."),

    ("What is a persistent volume and why does ChromaDB need one?",
     "A persistent volume is disk storage that survives container restarts and "
     "redeploys. ChromaDB writes its SQLite database and vector index to disk — "
     "without a volume, all data is lost every time the container restarts."),

    ("How do you store API keys securely in production?",
     "Never in code or git. In Railway: Settings → Variables → add each key. "
     "Railway injects them as environment variables at runtime. The app reads them "
     "via os.getenv(). The .env file stays local and gitignored."),

    ("What is a Dockerfile and why does Railway need one?",
     "A Dockerfile is a recipe for building a container image. It specifies "
     "the Python version, installs dependencies, copies the code, and defines "
     "the startup command. Railway reads it to build and run your app exactly "
     "as it runs locally — no 'works on my machine' issues."),

    ("What is the difference between Railway and a VPS (EC2)?",
     "Railway is Platform-as-a-Service: it manages servers, networking, TLS, "
     "and CI/CD for you. EC2 is Infrastructure-as-a-Service: you manage the OS, "
     "security patches, load balancers, everything. Railway trades control for "
     "convenience — right choice for a solo developer."),
]


def check_deployment_readiness():
    print("\n  Deployment readiness checklist")
    print("  " + "─" * 50)

    checks = [
        ("Dockerfile",            ROOT / "Dockerfile",            "Multi-stage production build"),
        ("docker-compose.yml",    ROOT / "docker-compose.yml",    "Two-container local setup"),
        (".dockerignore",         ROOT / ".dockerignore",         "Keeps .env out of image"),
        ("requirements.txt",      ROOT / "requirements.txt",      "Pinned dependencies"),
        (".env.example",          ROOT / ".env.example",          "Key template for new environments"),
        (".github/workflows/ci.yml", ROOT / ".github/workflows/ci.yml", "CI pipeline"),
    ]

    all_ok = True
    for name, path, desc in checks:
        ok = path.exists()
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {name:<30} {desc}")
        if not ok:
            all_ok = False

    return all_ok


def check_env_vars():
    print("\n  Environment variables (needed in Railway dashboard)")
    print("  " + "─" * 50)

    keys = [
        ("GEMINI_API_KEY",    "Required — Gemini AI"),
        ("TAVILY_API_KEY",    "Required — web search"),
        ("LANGSMITH_API_KEY", "Optional — tracing"),
    ]
    for k, desc in keys:
        val = os.getenv(k)
        mark = "✓" if val else "✗"
        display = f"{val[:6]}…" if val else "not set locally"
        print(f"  {mark}  {k:<22} {desc} ({display})")


def show_interview_qa():
    print("\n  Interview Q&A — hosting decisions")
    print("  " + "─" * 50)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 46 — Choosing Where to Host")
    print("  Decision: Railway (Docker + persistent volumes)")
    print("=" * 62)

    print(PLATFORM_TABLE)
    print(RAILWAY_SETUP)

    ready = check_deployment_readiness()
    check_env_vars()
    show_interview_qa()

    print("\n" + "=" * 62)
    print(f"  Deployment ready: {'Yes — proceed to Day 47' if ready else 'No — fix missing files first'}")
    print("  Next: python week8/day47_railway.py")
    print("=" * 62)
