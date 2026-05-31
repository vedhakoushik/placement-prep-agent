"""
Day 47 — Deploy to Railway
============================
ONE concept: push to GitHub → Railway builds your Docker image →
your app is live at a public URL. Zero server management.

What Railway does automatically:
  - Pulls latest code from GitHub on every push to main
  - Runs docker build using our Dockerfile
  - Starts the container with your environment variables
  - Gives you a HTTPS URL (free TLS certificate)
  - Restarts the container if it crashes

What we do manually (one-time setup):
  1. Create Railway account → railway.app
  2. New Project → Deploy from GitHub Repo
  3. Select this repo → Railway finds Dockerfile automatically
  4. Add environment variables (see below)
  5. Add a Volume for ChromaDB persistence
  6. Done — app is live

Deployment files in this repo:
  Dockerfile          — multi-stage build (already written, Day 43)
  railway.toml        — Railway-specific config (created today)
  .env.example        — documents which keys to add to Railway dashboard

Run:
  python week8/day47_railway.py   # prints setup guide + validates config
"""

import io
import subprocess
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent.parent


RAILWAY_STEPS = """
  Step-by-step Railway deployment
  ─────────────────────────────────────────────────────────────────

  1. Create account
     → railway.app → Sign in with GitHub

  2. New project
     → New Project → Deploy from GitHub Repo
     → Select: placement-prep-agent

  3. Railway detects Dockerfile automatically
     No Procfile needed. It reads our Dockerfile.

  4. Add environment variables
     → Your project → Variables tab → Add each key:

       GEMINI_API_KEY     = (from Google AI Studio)
       TAVILY_API_KEY     = (from tavily.com)
       LANGSMITH_API_KEY  = (optional, from smith.langchain.com)
       CHROMA_HOST        = (leave empty — embedded mode in production)

  5. Add a Volume for ChromaDB persistence
     → Your project → Add Plugin → Volume
     → Mount path: /app/chroma_db
     → Size: 1 GB (free tier)
     This makes ChromaDB data survive redeploys.

  6. Deploy
     Railway builds and deploys automatically.
     Check Logs tab — should see "Streamlit is running on port 8501"

  7. Get your URL
     → Settings → Domains → your-app.railway.app
     Share this link — it works for anyone with zero setup.

  8. Auto-deploy on push
     Every git push to main triggers a new build automatically.
     Bad deploy? Railway keeps the previous version running until
     the new build succeeds (zero-downtime deploys).
"""

RAILWAY_ENV_VARS = """
  Variables to add in Railway dashboard (Settings → Variables)
  ─────────────────────────────────────────────────────────────────
  Variable              Value
  ────────────────────  ──────────────────────────────────────────
  GEMINI_API_KEY        AIza...  (from Google AI Studio)
  TAVILY_API_KEY        tvly-...  (from tavily.com)
  LANGSMITH_API_KEY     ls__...  (optional)
  PORT                  8501  (Railway injects this automatically)

  Do NOT set CHROMA_HOST — the app uses embedded ChromaDB by default.
  Do NOT commit real keys — they live only in Railway's encrypted vault.
"""

VOLUME_SETUP = """
  ChromaDB Volume Setup
  ─────────────────────────────────────────────────────────────────
  Without a volume: every redeploy wipes ChromaDB (just like docker down -v)
  With a volume:    data persists across builds and restarts

  In Railway:
  → Project → + Add Service → Volume
  → Name: chroma-data
  → Mount path: /app/chroma_db
  → Size: 1 GB

  The app code reads CHROMA_PATH from env, defaulting to ./week3/qa_db locally
  and /app/chroma_db in Railway.
"""

INTERVIEW_QA = [
    ("How does Railway know how to start your app?",
     "Railway reads the CMD instruction at the bottom of our Dockerfile: "
     "'streamlit run week5/day34_35_app.py --server.port=8501 --server.address=0.0.0.0'. "
     "Everything else — installing Python, copying files, setting up the venv — "
     "happens during docker build before the container starts."),

    ("What is a zero-downtime deploy?",
     "Railway builds the new image while the old container keeps serving traffic. "
     "Only when the new container passes its health check does Railway switch the "
     "load balancer to the new one. Users never see a 'site is down' page."),

    ("How do you roll back a bad deployment?",
     "Railway keeps every build. In the Deployments tab, click any previous "
     "build → Rollback. The old container starts immediately. Then fix the bug, "
     "push a new commit, and the CI pipeline ensures tests pass before deploying."),

    ("Why not just deploy on your laptop?",
     "Local machines go offline, IP addresses change, there's no HTTPS, and you'd "
     "need to leave it running 24/7. Cloud hosting gives a stable URL, TLS, auto-restart "
     "on crash, and you can close your laptop without breaking the app."),
]


def check_railway_config():
    print("\n  Railway config files")
    print("  " + "─" * 50)

    files = {
        "railway.toml":   "Railway build + start config",
        "Dockerfile":     "Container definition (auto-detected)",
        ".dockerignore":  "Keeps .env and .venv out of image",
        "requirements.txt": "Pinned dependencies for reproducible builds",
    }
    all_ok = True
    for f, desc in files.items():
        path = ROOT / f
        ok   = path.exists()
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {f:<22} {desc}")
        if not ok:
            all_ok = False
    return all_ok


def check_git_remote():
    print("\n  Git remote (needed for Railway GitHub integration)")
    print("  " + "─" * 50)
    try:
        out = subprocess.run(["git", "remote", "-v"],
                             capture_output=True, text=True, cwd=str(ROOT))
        for line in out.stdout.strip().splitlines()[:2]:
            print(f"  {line}")
    except Exception as e:
        print(f"  Error: {e}")


def show_interview_qa():
    print("\n  Interview Q&A — deployment")
    print("  " + "─" * 50)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")


if __name__ == "__main__":
    print("=" * 62)
    print("  Day 47 — Deploy to Railway")
    print("  Target: placement-prep-agent.railway.app")
    print("=" * 62)

    print(RAILWAY_STEPS)
    print(RAILWAY_ENV_VARS)
    print(VOLUME_SETUP)

    ok = check_railway_config()
    check_git_remote()
    show_interview_qa()

    print("\n" + "=" * 62)
    status = "✓ Config files present — ready to deploy" if ok else "✗ Fix missing files first"
    print(f"  Status: {status}")
    print("  After deploying, your URL will be:")
    print("  → https://placement-prep-agent.railway.app")
    print("=" * 62)
