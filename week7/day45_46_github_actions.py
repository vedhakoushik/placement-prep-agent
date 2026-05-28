"""
Day 45-46 -- GitHub Actions CI/CD
===================================
ONE concept: GitHub Actions lets you automate anything — tests, linting,
Docker builds, deployments — triggered by git events (push, PR, schedule).
Your pipeline lives in code, versioned alongside your app.

What is NEW today:
  1. Workflow anatomy       -- on / jobs / steps / uses / run
  2. Job sequencing         -- needs: prevents deploy if tests fail
  3. Matrix strategy        -- test against multiple Python versions in parallel
  4. Secrets & environments -- GITHUB_TOKEN (free) vs repo secrets
  5. GitHub Step Summary    -- custom Markdown tables in workflow output
  6. Concurrency control    -- queue deploys, never run two at once
  7. Caching                -- pip cache + Docker layer cache (type=gha)

Key files:
  .github/workflows/ci.yml      -- lint → unit → integration → docker build
  .github/workflows/deploy.yml  -- test → build image → push → Railway deploy

Run:
  python week7/day45_46_github_actions.py   # prints concept summary + checks files
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  CONCEPT EXPLAINERS
# ═══════════════════════════════════════════════════════════════
WORKFLOW_ANATOMY = """
  Workflow anatomy
  ────────────────

  .github/workflows/ci.yml
  │
  ├─ name: CI                        ← display name in GitHub UI
  │
  ├─ on:                             ← TRIGGER
  │    push:
  │      branches: ["**"]            ← every branch
  │    pull_request:
  │      branches: ["**"]
  │
  └─ jobs:
       lint:                         ← JOB (runs in its own VM)
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v4        ← ACTION (reusable unit)
           - uses: actions/setup-python@v5
             with:
               python-version: "3.11"
               cache: pip             ← pip cache across runs
           - name: Run ruff
             run: ruff check .        ← SHELL COMMAND

  Key vocabulary:
    Workflow  = YAML file in .github/workflows/
    Job       = group of steps that share one runner VM
    Step      = single action or shell command
    Action    = reusable community/official plugin (uses:)
    Runner    = VM that executes the job (ubuntu-latest, windows-latest)
    Trigger   = event that starts the workflow (push, PR, schedule, manual)
"""

JOB_SEQUENCING = """
  Job sequencing with needs:
  ──────────────────────────

  jobs:
    lint:           # runs first (no needs:)
      ...

    unit-tests:
      needs: lint   # waits for lint to succeed

    integration-tests:
      needs: unit-tests   # chain: lint -> unit -> integration

    docker-build:
      needs: unit-tests   # parallel with integration-tests

    ci-summary:
      needs: [lint, unit-tests, integration-tests, docker-build]
      if: always()   # run even if a job fails — report everything

  Why this matters:
    - Fastest feedback first (lint is cheap)
    - No wasted compute (don't build Docker if tests fail)
    - Parallel where possible (docker-build + integration run together)
"""

MATRIX_STRATEGY = """
  Matrix strategy — test multiple versions at once
  ─────────────────────────────────────────────────

  unit-tests:
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

  Result: THREE parallel jobs spin up automatically:
    unit-tests (3.10) │ unit-tests (3.11) │ unit-tests (3.12)

  The matrix values substitute into every step automatically.
  Use matrix for: Python versions, OS combos, browser types.
"""

SECRETS_GUIDE = """
  Secrets & environments
  ──────────────────────

  Types of secrets:
    GITHUB_TOKEN     auto-injected, no setup — push to ghcr.io
    Repo secrets     Settings → Secrets → Actions → New secret
    Environment      Settings → Environments → production → add secret
                     Extra protection: require reviewer approval before deploy

  Using secrets in YAML:
    env:
      RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
      API_KEY:       ${{ secrets.GEMINI_API_KEY }}

  Rules:
    * Never echo secrets in logs — GitHub masks them, but don't try
    * Never store secrets in code or Dockerfile ENV
    * Use .env for local dev, GitHub secrets for CI, Railway env vars for prod
    * GITHUB_TOKEN has write:packages permission only if you grant it:
        permissions:
          packages: write

  Environments:
    environment: production     # links to the "production" environment
    → adds a deployment record in GitHub UI
    → can require manual approval before secrets are released
"""

CACHING = """
  Caching in Actions
  ──────────────────

  pip cache (via actions/setup-python):
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
        cache: pip              ← caches ~/.cache/pip automatically

  Docker layer cache (via BuildKit + GHA cache):
    - uses: docker/build-push-action@v5
      with:
        cache-from: type=gha    ← read layers from Actions cache
        cache-to: type=gha,mode=max  ← write all layers back

  Result: a cold Docker build (~3 min) drops to ~30s on second run
  because only changed layers are rebuilt.

  Key insight: layer caching only works if your Dockerfile is ordered
  correctly — requirements.txt BEFORE source code (see day43_44_docker.py).
"""

STEP_SUMMARY = """
  GitHub Step Summary — custom UI in the Actions tab
  ────────────────────────────────────────────────────

  Any step can write Markdown to $GITHUB_STEP_SUMMARY:

    - name: CI Summary
      run: |
        echo "## CI Results" >> $GITHUB_STEP_SUMMARY
        echo "| Job | Status |"         >> $GITHUB_STEP_SUMMARY
        echo "|-----|--------|"         >> $GITHUB_STEP_SUMMARY
        echo "| Lint | ${{ needs.lint.result }} |" >> $GITHUB_STEP_SUMMARY

  GitHub renders this as a formatted table in the workflow run UI.
  Useful for: test counts, coverage %, deployment URLs, image sizes.
"""

CONCURRENCY = """
  Concurrency control — never deploy twice at once
  ─────────────────────────────────────────────────

  concurrency:
    group: deploy-production      ← name of the group
    cancel-in-progress: false     ← queue, don't cancel mid-deploy

  vs.

  concurrency:
    group: pr-${{ github.head_ref }}
    cancel-in-progress: true      ← cancel old CI runs when you push a new commit
                                    (common for PR workflows — saves minutes)

  Use cancel-in-progress: false for deploys (never interrupt).
  Use cancel-in-progress: true for CI on PRs (always test latest commit only).
"""


# ═══════════════════════════════════════════════════════════════
#  FILE VALIDATOR
# ═══════════════════════════════════════════════════════════════
def validate_workflow_files():
    print("\n  GitHub Actions file checklist")
    print("  " + "-" * 42)

    files = {
        ".github/workflows/ci.yml":     "Lint → test → docker build pipeline",
        ".github/workflows/deploy.yml": "Build image → push → Railway deploy",
    }

    all_ok = True
    for rel, desc in files.items():
        path = ROOT / rel
        exists = path.exists()
        mark = "OK" if exists else "X "
        print(f"  {mark}  {rel:<36} {desc}")
        if not exists:
            all_ok = False

    return all_ok


def check_git_remote():
    """Check if this repo has a GitHub remote set up."""
    print("\n  Git remote")
    print("  " + "-" * 42)
    try:
        out = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True, text=True, timeout=5, cwd=ROOT
        )
        if out.returncode == 0 and "github.com" in out.stdout:
            lines = [l for l in out.stdout.strip().splitlines() if l]
            print(f"  OK  {lines[0].split()[1]}")
            return True
        elif out.returncode == 0:
            print("  --  No GitHub remote found (local only)")
            return False
        else:
            print("  X   git command failed")
            return False
    except FileNotFoundError:
        print("  X   git not installed")
        return False


def show_next_steps():
    print("\n  Next steps — to activate your pipelines")
    print("  " + "-" * 42)
    steps = [
        ("Push to GitHub",          "git push origin main"),
        ("Watch CI",                "github.com/<you>/<repo>/actions"),
        ("Add RAILWAY_TOKEN",       "GitHub → Settings → Secrets → Actions"),
        ("Add GEMINI_API_KEY",      "GitHub → Settings → Secrets → Actions"),
        ("Add TAVILY_API_KEY",      "GitHub → Settings → Secrets → Actions"),
        ("Manual deploy trigger",   "Actions → Deploy → Run workflow"),
    ]
    for label, detail in steps:
        print(f"  {label:<28}  {detail}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Day 45-46 -- GitHub Actions CI/CD")
    print("  NEW: workflows, matrix, secrets, caching, concurrency")
    print("=" * 60)

    print(WORKFLOW_ANATOMY)
    print(JOB_SEQUENCING)
    print(MATRIX_STRATEGY)
    print(SECRETS_GUIDE)
    print(CACHING)
    print(STEP_SUMMARY)
    print(CONCURRENCY)

    files_ok  = validate_workflow_files()
    remote_ok = check_git_remote()

    show_next_steps()

    print("\n" + "=" * 60)
    print("  Summary")
    print("  Workflow files:    ", "Yes" if files_ok  else "No  -- check .github/workflows/")
    print("  GitHub remote:     ", "Yes" if remote_ok else "No  -- push to GitHub to activate")
    print()
    print("  Key rule: needs: chains jobs so broken tests block deploys")
    print("  Key rule: secrets stay in GitHub, never in YAML or code")
    print("  Key rule: cancel-in-progress: false for deploy, true for PR CI")
    print("=" * 60)
