"""
Day 44-45 -- CI/CD with GitHub Actions
========================================
ONE concept: every push to main automatically runs your tests and builds
your Docker image. If anything breaks, the push is flagged before it
reaches production. This is the safety net every real team uses.

CI = Continuous Integration  → tests run on every commit
CD = Continuous Deployment   → passing tests auto-deploy to production

What is in our pipeline (.github/workflows/ci.yml):
  Job 1: Lint (ruff)          — catches syntax errors and style issues
  Job 2: Unit tests           — 21 tests, mocked APIs, runs in ~17s
  Job 3: Integration tests    — 18 tests, real LangGraph, temp SQLite
  Job 4: Docker build         — proves the image actually builds
  Job 5: CI Summary           — Markdown table in GitHub Actions UI

Pipeline order (needs:):
  lint → unit-tests → integration-tests → ci-summary
                    ↘ docker-build ──────────────↗

Interview talking points:
  Q: "What is CI/CD?"
  A: CI (Continuous Integration) means every commit is automatically
     tested before merging. CD (Continuous Deployment) means passing
     commits are automatically deployed to production. Together they
     eliminate manual steps and catch regressions instantly.

  Q: "What happens when a test fails in CI?"
  A: The pipeline stops at the failing job. Later jobs (like deploy)
     never run. GitHub marks the commit red and emails the author.
     The team sees exactly which test failed and why, with full logs.

  Q: "Why not just run tests locally?"
  A: Local environments differ. CI runs in a clean, standardised
     container (ubuntu-latest) every time. It catches issues like
     'works on my machine' — missing env vars, wrong Python version,
     uncommitted files.

  Q: "What is a job? What is a step?"
  A: A job is a group of steps that runs on one virtual machine.
     Steps are individual shell commands or community actions.
     Jobs run in parallel unless you add needs: to chain them.

  Q: "What is needs: in GitHub Actions?"
  A: needs: makes one job wait for another to succeed before starting.
     Example: needs: unit-tests means docker-build only runs if
     unit-tests passes. This prevents wasting compute on later
     stages when early stages fail.

Demo task completed:
  1. Pushed a BREAKING CHANGE — deliberate failing test
     → CI turned red (all jobs after unit-tests skipped)
  2. Pushed the FIX — removed the broken test
     → CI turned green (all 5 jobs passed)
  Both screenshots saved for portfolio.

Run:
  python week7/day44_45_cicd.py   # prints this summary
  # To watch your own CI: github.com/<you>/placement-prep-agent/actions
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent
CI_FILE = ROOT / ".github" / "workflows" / "ci.yml"

INTERVIEW_QA = [
    ("What does CI stand for and what does it mean?",
     "Continuous Integration — every commit is automatically tested "
     "before it can affect others. Tests run in a clean cloud VM on every push."),

    ("What does CD stand for?",
     "Continuous Deployment — after tests pass, code is automatically "
     "deployed to production without manual steps."),

    ("What is a GitHub Actions workflow?",
     "A YAML file in .github/workflows/ that defines triggers (on: push) "
     "and jobs. Each job runs on a cloud VM and contains steps."),

    ("What is the difference between a job and a step?",
     "A job is a VM instance (runs in parallel with other jobs by default). "
     "A step is a single command or action inside a job (runs sequentially)."),

    ("What does needs: do?",
     "Creates a dependency between jobs. needs: unit-tests means "
     "docker-build only starts if unit-tests succeeds."),

    ("Why is CI better than just running tests locally?",
     "CI is clean — no local state, no uncommitted files. "
     "It catches 'works on my machine' bugs and ensures every team member's "
     "commit is tested the same way."),

    ("What happens when a CI job fails?",
     "That job is marked red. All jobs that need: it are skipped. "
     "GitHub sends an email to the committer. The commit is blocked from "
     "auto-deploy. The team sees exactly which step failed with full logs."),
]


def show_pipeline():
    print("\n  Our CI pipeline")
    print("  " + "─" * 46)
    jobs = [
        ("1", "Lint (ruff)",        "catches style + syntax errors",   "7s"),
        ("2", "Unit tests",         "21 mocked tests",                 "17s"),
        ("3", "Integration tests",  "18 LangGraph tests + SqliteSaver","25s"),
        ("4", "Docker build",       "proves image builds end-to-end",  "90s"),
        ("5", "CI Summary",         "Markdown table in Actions UI",    "2s"),
    ]
    for num, name, desc, duration in jobs:
        print(f"  Job {num}: {name:<22} {desc:<38} ~{duration}")
    print()
    print("  Flow: lint → unit-tests → integration-tests → ci-summary")
    print("                         ↘ docker-build ──────────────↗")


def show_interview_qa():
    print("\n  Interview Q&A")
    print("  " + "─" * 46)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")


def check_ci_file():
    print("\n  CI file check")
    print("  " + "─" * 46)
    if CI_FILE.exists():
        lines = CI_FILE.read_text(encoding="utf-8").splitlines()
        print(f"  OK  {CI_FILE.relative_to(ROOT)}  ({len(lines)} lines)")
    else:
        print(f"  X   {CI_FILE} not found")


if __name__ == "__main__":
    print("=" * 58)
    print("  Day 44-45 -- CI/CD with GitHub Actions")
    print("  CI = test every commit | CD = auto-deploy on green")
    print("=" * 58)

    show_pipeline()
    show_interview_qa()
    check_ci_file()

    print("\n" + "=" * 58)
    print("  Key rules:")
    print("  1. Tests run on EVERY push — no exceptions")
    print("  2. needs: chains jobs — later jobs skip if earlier fail")
    print("  3. Secrets in GitHub Settings, never in YAML")
    print("  4. CI is the safety net — deploy only on green")
    print("=" * 58)
