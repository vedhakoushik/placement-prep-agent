"""
Day 48-49 -- Cloud Deployment (Railway)
=========================================
ONE concept: deploying a Dockerised app to the cloud means giving Railway
(or Render/Fly.io) your Dockerfile and environment variables — it handles
the server, HTTPS, domain, and auto-restarts.

What is NEW today:
  1. Railway overview        -- project / service / environment model
  2. Deployment methods      -- CLI (railway up) vs GitHub auto-deploy
  3. Environment variables   -- set in dashboard, injected at runtime
  4. Custom domain & HTTPS   -- Railway provides *.up.railway.app free
  5. Render alternative      -- Dockerfile deploy, free tier available
  6. Fly.io alternative      -- fly.toml, fly deploy, global regions
  7. Rollback strategy       -- re-deploy a previous image tag

Alternatives at a glance:
  Platform   Free tier   Build from   Best for
  Railway    500h/month  Dockerfile   Hobby / startup, easy CLI
  Render     750h/month  Dockerfile   Streamlit apps, auto-sleep
  Fly.io     3 VMs free  Dockerfile   Global edge, multi-region
  GCP Run    2M reqs     Docker image  Serverless, pay-per-request
  AWS ECS    Fargate     ECR image     Enterprise, full control

Run:
  python week8/day48_49_cloud_deploy.py   # prints concept summary
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  CONCEPT EXPLAINERS
# ═══════════════════════════════════════════════════════════════
RAILWAY_OVERVIEW = """
  Railway — key concepts
  ──────────────────────

  Project     = top-level container (one per app)
  Service     = one deployable unit inside a project (your Docker app)
  Environment = isolated copy of the project (production / staging)
  Variable    = env var set in dashboard, injected at runtime

  How Railway deploys:
    1. You push to GitHub main (or run railway up)
    2. Railway detects Dockerfile
    3. Builds the image (using Buildkit, same as local)
    4. Starts a container, injects Variables, maps a port
    5. Exposes https://<app>.up.railway.app

  Pricing:
    Free tier: 500 execution hours per month
    Pro: $20/month for unlimited + private networking

  Railway automatically:
    - Issues TLS/HTTPS certificate
    - Restarts container on crash (HEALTHCHECK helps routing)
    - Provides metrics (CPU, memory, network)
"""

RAILWAY_CLI = """
  Railway CLI — deploy from terminal
  ────────────────────────────────────

  Install:
    npm install -g @railway/cli    # or: brew install railway

  Setup:
    railway login                  # opens browser for auth
    railway init                   # creates project (run once)
    railway link                   # link existing project

  Deploy:
    railway up                     # build + deploy current dir
    railway up --service myapp     # target specific service
    railway up --detach            # async (don't wait for build)

  Logs:
    railway logs                   # tail live logs
    railway logs --tail 100        # last 100 lines

  Variables:
    railway variables              # list all vars
    railway variables set KEY=val  # set one variable

  Status:
    railway status                 # show current deployment
    railway open                   # open app in browser

  Used in deploy.yml job 3:
    railway up --service placement-prep --detach
"""

ENV_VARS_SETUP = """
  Setting environment variables in Railway
  ─────────────────────────────────────────

  Dashboard method (recommended for secrets):
    1. railway.app → your project → Variables tab
    2. Click + New Variable
    3. Add each key:
         GEMINI_API_KEY    = [your real key]
         TAVILY_API_KEY    = [your real key]
    4. Deploy — Railway injects them automatically

  CLI method:
    railway variables set GEMINI_API_KEY=AIza...
    railway variables set TAVILY_API_KEY=tvly-...

  Never:
    - Add keys to railway.toml or Dockerfile
    - Commit .env to git and push

  Verification:
    railway variables   # shows all vars (values are masked)
"""

RENDER_ALTERNATIVE = """
  Render — alternative to Railway
  ────────────────────────────────

  Free tier: 750h/month (enough for one always-on service)
  Auto-sleep: free services sleep after 15 min inactivity

  Setup:
    1. render.com → New → Web Service
    2. Connect GitHub repo
    3. Build command: (blank — uses Dockerfile)
    4. Start command: (blank — uses CMD from Dockerfile)
    5. Add Environment Variables in dashboard
    6. Deploy

  Custom domain:
    Dashboard → Custom Domains → add your domain → update DNS CNAME

  Best for Streamlit apps because:
    - Free tier is generous
    - Auto-deploys from GitHub on push
    - HTTPS included, no config needed
"""

FLY_ALTERNATIVE = """
  Fly.io — alternative for global edge deployment
  ─────────────────────────────────────────────────

  Setup:
    brew install flyctl
    fly auth login
    fly launch           # auto-detects Dockerfile, creates fly.toml

  fly.toml (auto-generated, edit as needed):
    app = "placement-prep"
    primary_region = "lhr"    # London — pick closest to users

    [http_service]
      internal_port = 8501
      force_https = true
      auto_stop_machines = true

    [[vm]]
      cpu_kind = "shared"
      cpus = 1
      memory_mb = 512

  Deploy:
    fly deploy             # builds + deploys
    fly logs               # tail logs
    fly secrets set GEMINI_API_KEY=AIza...

  Rollback:
    fly releases           # list past releases
    fly deploy --image registry.fly.io/myapp:v2   # re-deploy old image
"""

ROLLBACK_STRATEGY = """
  Rollback strategy — when a deploy breaks production
  ────────────────────────────────────────────────────

  Option 1 — Re-deploy previous Git commit:
    git revert HEAD            # create a revert commit
    git push origin main       # triggers new deploy

  Option 2 — Re-deploy a specific Docker image tag:
    # your deploy.yml tags images: latest + sha-XXXXXXX
    # Railway: dashboard → Deployments → click previous → Redeploy
    # Fly.io:  fly deploy --image registry.fly.io/myapp:sha-abc123

  Option 3 — Railway one-click rollback:
    Dashboard → Deployments → previous entry → "Redeploy"
    (Railway keeps last 10 deployments)

  Blue-green (advanced):
    - Keep two Railway environments: production + staging
    - Deploy to staging first, smoke test, then promote

  Prevention beats cure:
    - Never deploy without tests passing (enforced by needs: in deploy.yml)
    - Use deploy.yml's environment: production for manual approval gate
    - HEALTHCHECK in Dockerfile — Railway won't route traffic to unhealthy containers
"""


# ═══════════════════════════════════════════════════════════════
#  CHECKLIST
# ═══════════════════════════════════════════════════════════════
def show_deploy_checklist():
    print("\n  Pre-deploy checklist")
    print("  " + "-" * 44)

    checks = [
        ("Dockerfile exists",             (ROOT / "Dockerfile").exists()),
        (".env.example committed",        (ROOT / ".env.example").exists()),
        (".gitignore has .env rule",      _gitignore_has_env()),
        ("ci.yml exists",                 (ROOT / ".github/workflows/ci.yml").exists()),
        ("deploy.yml exists",             (ROOT / ".github/workflows/deploy.yml").exists()),
        ("HEALTHCHECK in Dockerfile",     _dockerfile_has_healthcheck()),
    ]

    for label, ok in checks:
        mark = "OK" if ok else "--"
        print(f"  {mark}  {label}")


def _gitignore_has_env():
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return False
    return ".env" in gi.read_text(encoding="utf-8", errors="replace")


def _dockerfile_has_healthcheck():
    df = ROOT / "Dockerfile"
    if not df.exists():
        return False
    return "HEALTHCHECK" in df.read_text(encoding="utf-8", errors="replace")


def show_platform_comparison():
    print("\n  Platform comparison")
    print("  " + "-" * 60)
    rows = [
        ("Railway",   "500h free", "Dockerfile", "Easy CLI, instant"),
        ("Render",    "750h free", "Dockerfile", "Auto-sleep, generous"),
        ("Fly.io",    "3 VMs",     "Dockerfile", "Global, multi-region"),
        ("GCP Run",   "2M reqs",   "Docker img", "Serverless, cold start"),
        ("AWS ECS",   "Pay-as",    "ECR image",  "Enterprise, full ctrl"),
    ]
    print(f"  {'Platform':<12} {'Free Tier':<14} {'Build From':<14} {'Notes'}")
    print(f"  {'-'*12} {'-'*14} {'-'*14} {'-'*22}")
    for name, free, build, notes in rows:
        print(f"  {name:<12} {free:<14} {build:<14} {notes}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 48-49 -- Cloud Deployment (Railway)")
    print("  NEW: railway CLI, env vars, Render/Fly alternatives, rollback")
    print("=" * 60)

    print(RAILWAY_OVERVIEW)
    print(RAILWAY_CLI)
    print(ENV_VARS_SETUP)
    print(RENDER_ALTERNATIVE)
    print(FLY_ALTERNATIVE)
    print(ROLLBACK_STRATEGY)

    show_deploy_checklist()
    show_platform_comparison()

    print("\n" + "=" * 60)
    print("  Summary")
    print()
    print("  Key rule: env vars in dashboard, never in Dockerfile or git")
    print("  Key rule: HEALTHCHECK stops bad deploys getting traffic")
    print("  Key rule: rollback = redeploy old image tag, no config change")
    print("  Quick start: railway login → railway link → railway up")
    print("=" * 60)
