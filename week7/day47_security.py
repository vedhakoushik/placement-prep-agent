"""
Day 47 -- Security & Secrets Management
=========================================
ONE concept: secrets (API keys, tokens, passwords) must NEVER be committed
to git or baked into Docker images. Use environment variables everywhere —
different values per environment, injected at runtime.

What is NEW today:
  1. .env + python-dotenv    -- local dev secrets, never committed
  2. .gitignore protection   -- stop .env from ever reaching GitHub
  3. Docker secret rules     -- ENV bakes values into image history
  4. GitHub Secrets          -- CI/CD secrets, masked in logs
  5. Railway env vars        -- production secrets, never in code
  6. Secret rotation         -- how to change a key without downtime
  7. validate_env()          -- startup check catches missing keys early

Key rules remembered as "NEVER-LOAD-ROTATE":
  N - Never commit .env or any file with real keys
  E - Env vars only — no hardcoded strings in source
  V - Validate at startup (fail fast before doing work)
  E - Each environment has its OWN values (dev != prod)
  R - Rotate keys regularly and immediately after a breach

Run:
  python week7/day47_security.py   # prints summary + audits your repo
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  CONCEPT EXPLAINERS
# ═══════════════════════════════════════════════════════════════
DOTENV_GUIDE = """
  .env + python-dotenv
  ─────────────────────

  .env (local only, NEVER committed):
    GEMINI_API_KEY=AIza...your_real_key...
    TAVILY_API_KEY=tvly-...your_real_key...

  .env.example (committed — safe template):
    GEMINI_API_KEY=your_gemini_key_here
    TAVILY_API_KEY=your_tavily_key_here

  In Python:
    from dotenv import load_dotenv
    import os

    load_dotenv()                      # reads .env into os.environ
    key = os.getenv("GEMINI_API_KEY")  # None if missing (safe default)

  Always use os.getenv("KEY") not os.environ["KEY"]
    os.environ["KEY"]  -- raises KeyError if missing (crashes)
    os.getenv("KEY")   -- returns None if missing (handle gracefully)
    os.getenv("KEY", "default")  -- fallback value

  Workflow:
    1. cp .env.example .env
    2. Edit .env with real keys
    3. Never git add .env
"""

GITIGNORE_RULES = """
  .gitignore — stop secrets reaching GitHub
  ──────────────────────────────────────────

  Critical lines in .gitignore:
    .env
    *.env
    .env.*
    !.env.example     <- allow the template through

  Verify nothing slipped through:
    git ls-files | grep -i "\.env"   # should return NOTHING except .env.example

  If you accidentally committed a secret:
    1. Rotate the key IMMEDIATELY (assume it's already stolen)
    2. git rm --cached .env
    3. git commit -m "remove accidentally tracked .env"
    4. git push
    Note: the key is still in git history — rotation is the only real fix.

  BFG Repo Cleaner (nuclear option — rewrites history):
    brew install bfg
    bfg --delete-files .env
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive
    git push --force   # destructive — coordinate with team first
"""

DOCKER_SECRET_RULES = """
  Docker secret rules
  ────────────────────

  WRONG — bakes key into every image layer:
    ENV GEMINI_API_KEY=AIza...real_key...   # visible in docker history!

  WRONG — COPY .env into image:
    COPY .env .                              # .env ends up in image

  RIGHT — inject at runtime:
    docker run --env-file .env placement-prep
    # or
    docker run -e GEMINI_API_KEY=$GEMINI_API_KEY placement-prep

  RIGHT — docker compose reads from host env or .env file:
    services:
      app:
        env_file: - .env   # reads .env from host at start time

  Check what's in an image:
    docker history placement-prep   # shows every layer command
    docker inspect placement-prep   # shows Env[] in Config section

  Rule: if "docker inspect" shows your key, rebuild without it.
"""

GITHUB_SECRETS = """
  GitHub Secrets — CI/CD injection
  ──────────────────────────────────

  Where to add:
    GitHub repo → Settings → Secrets and variables → Actions → New secret

  In ci.yml / deploy.yml:
    env:
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}

  In a step:
    - name: Run tests
      env:
        GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      run: pytest ...

  GitHub masks secrets in logs: if a secret value appears in output,
  GitHub replaces it with "***". But still don't print secrets.

  Types:
    Repository secrets   -- available to all workflows in the repo
    Environment secrets  -- only released when the "environment" matches
                           (used in deploy.yml → environment: production)
    Organization secrets -- shared across all repos in an org
"""

RAILWAY_SECRETS = """
  Railway env vars — production secrets
  ──────────────────────────────────────

  Where to add:
    railway.app → project → service → Variables → + New Variable

  Keys to add:
    GEMINI_API_KEY    your real Gemini key
    TAVILY_API_KEY    your real Tavily key
    LANGSMITH_API_KEY (optional)

  Railway injects these as environment variables at runtime.
  They are NOT visible in your repo, Dockerfile, or logs.

  The flow:
    Local dev:  .env  (on your machine only)
    CI tests:   GitHub Secrets  (mocked in unit tests, real in integration)
    Production: Railway Variables  (real keys, injected by Railway)
"""

VALIDATE_ENV_PATTERN = """
  validate_env() — fail fast at startup
  ───────────────────────────────────────

  # src/utils.py already has this — copy is here for reference
  import os

  REQUIRED_KEYS = ["GEMINI_API_KEY", "TAVILY_API_KEY"]
  OPTIONAL_KEYS = ["LANGSMITH_API_KEY", "LANGCHAIN_PROJECT"]

  def validate_env(raise_on_missing: bool = True) -> dict[str, bool]:
      results = {}
      missing = []
      for key in REQUIRED_KEYS:
          present = bool(os.getenv(key))
          results[key] = present
          if not present:
              missing.append(key)
      for key in OPTIONAL_KEYS:
          results[key] = bool(os.getenv(key))

      if raise_on_missing and missing:
          raise EnvironmentError(
              f"Missing required env vars: {missing}\\n"
              f"Copy .env.example to .env and fill in your keys."
          )
      return results

  Where to call it:
    main.py   -- at the top of main(), before any API calls
    app.py    -- in page_research() before kicking off a pipeline run
    tests     -- in conftest.py with raise_on_missing=False to skip gracefully
"""

SECRET_ROTATION = """
  Secret rotation — when and how
  ────────────────────────────────

  When to rotate:
    * Someone left the team
    * Key was accidentally logged or committed
    * Suspected breach
    * Provider recommends it (some rotate every 90 days)

  How to rotate with zero downtime:
    1. Generate NEW key from provider dashboard
    2. Add new key to Railway Variables (Railway deploys automatically)
    3. Update GitHub Secrets (next CI run picks it up)
    4. Update your local .env
    5. Revoke the OLD key (after confirming new key works)

  Order matters: add new BEFORE revoking old.
  Never delete old without testing new — brief dual-key window is safe.
"""


# ═══════════════════════════════════════════════════════════════
#  SECURITY AUDITOR
# ═══════════════════════════════════════════════════════════════
def audit_gitignore():
    """Check .gitignore protects .env files."""
    print("\n  .gitignore audit")
    print("  " + "-" * 44)

    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        print("  X   .gitignore not found -- create it now!")
        return False

    content = gitignore.read_text(encoding="utf-8", errors="replace")
    checks = [
        (".env",          ".env" in content),
        ("*.env",         "*.env" in content),
        ("!.env.example", "!.env.example" in content),
    ]

    all_ok = True
    for rule, present in checks:
        mark = "OK" if present else "X "
        print(f"  {mark}  {rule}")
        if not present:
            all_ok = False

    return all_ok


def audit_tracked_secrets():
    """Check git isn't tracking any .env files."""
    print("\n  Git-tracked secret files")
    print("  " + "-" * 44)
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, timeout=5, cwd=ROOT
        )
        if out.returncode != 0:
            print("  --  git ls-files failed (not a git repo?)")
            return True

        tracked = [
            line for line in out.stdout.splitlines()
            if ".env" in line.lower() and ".env.example" not in line
        ]

        if tracked:
            print("  X   These secret files are tracked by git:")
            for f in tracked:
                print(f"        {f}")
            print("  Fix: git rm --cached <file>  then  git commit")
            return False
        else:
            print("  OK  No .env files tracked by git")
            return True
    except FileNotFoundError:
        print("  --  git not installed")
        return True


def audit_env_example():
    """Check .env.example has no real keys."""
    print("\n  .env.example key check")
    print("  " + "-" * 44)

    path = ROOT / ".env.example"
    if not path.exists():
        print("  X   .env.example not found")
        return False

    content = path.read_text(encoding="utf-8", errors="replace")
    suspicious = []
    for line in content.splitlines():
        if "=" in line and not line.startswith("#"):
            _, _, val = line.partition("=")
            val = val.strip()
            # Real keys are typically long and not placeholder text
            if len(val) > 30 and not any(w in val.lower() for w in ["your", "here", "example", "xxx"]):
                suspicious.append(line)

    if suspicious:
        print("  X   Possible real keys in .env.example:")
        for line in suspicious:
            print(f"      {line[:60]}...")
        return False
    else:
        print("  OK  .env.example looks safe (only placeholder values)")
        return True


def audit_dockerfile():
    """Check Dockerfile doesn't bake secrets."""
    print("\n  Dockerfile secret check")
    print("  " + "-" * 44)

    dockerfile = ROOT / "Dockerfile"
    if not dockerfile.exists():
        print("  --  Dockerfile not found (create it in day43_44_docker.py)")
        return True

    content = dockerfile.read_text(encoding="utf-8", errors="replace")
    issues = []

    if "COPY .env" in content:
        issues.append("COPY .env  -- removes .env from image")

    # Check for ENV lines with suspicious values (long strings after =)
    for line in content.splitlines():
        if line.strip().startswith("ENV") and "=" in line:
            parts = line.split("=", 1)
            if len(parts) > 1:
                val = parts[1].strip()
                if len(val) > 20 and not val.startswith("$"):
                    issues.append(f"Possible hardcoded secret: {line.strip()[:60]}")

    if issues:
        print("  X   Issues found:")
        for issue in issues:
            print(f"      {issue}")
        return False
    else:
        print("  OK  Dockerfile does not bake secrets (no COPY .env, no hardcoded ENV)")
        return True


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 47 -- Security & Secrets Management")
    print("  NEVER-LOAD-ROTATE: commit, env-only, validate, envs, rotate")
    print("=" * 60)

    print(DOTENV_GUIDE)
    print(GITIGNORE_RULES)
    print(DOCKER_SECRET_RULES)
    print(GITHUB_SECRETS)
    print(RAILWAY_SECRETS)
    print(VALIDATE_ENV_PATTERN)
    print(SECRET_ROTATION)

    gi_ok      = audit_gitignore()
    track_ok   = audit_tracked_secrets()
    example_ok = audit_env_example()
    docker_ok  = audit_dockerfile()

    all_ok = gi_ok and track_ok and example_ok and docker_ok

    print("\n" + "=" * 60)
    print("  Security Audit Summary")
    print(f"  .gitignore rules:       {'Pass' if gi_ok      else 'FAIL -- add .env rules'}")
    print(f"  Git-tracked secrets:    {'Pass' if track_ok   else 'FAIL -- git rm --cached'}")
    print(f"  .env.example safe:      {'Pass' if example_ok else 'FAIL -- check for real keys'}")
    print(f"  Dockerfile clean:       {'Pass' if docker_ok  else 'FAIL -- remove ENV/COPY .env'}")
    print()
    if all_ok:
        print("  All checks passed -- your secrets are safe.")
    else:
        print("  Fix the items above before pushing to GitHub.")
    print()
    print("  Key rule: commit .env.example, NEVER .env")
    print("  Key rule: rotate immediately if a key leaks")
    print("  Key rule: validate_env() at startup -- fail fast")
    print("=" * 60)
