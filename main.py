#!/usr/bin/env python3
"""
main.py — Placement Prep Agent CLI  (Day 41)
=============================================
Single entry point for the entire project.

Usage:
    python main.py research --company Google --role SDE-2 --focus DSA
    python main.py ui
    python main.py test
    python main.py env

Commands:
    research   Run the research agent (terminal output)
    ui         Launch the Streamlit web UI
    test       Run the full test suite
    env        Validate .env file and print key status
"""

import io
import os
import sys
import argparse
import subprocess
from pathlib import Path
from dotenv  import load_dotenv

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ═══════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════
def cmd_env(args):
    """Validate .env and print key status."""
    from src.utils import validate_env, REQUIRED_KEYS, OPTIONAL_KEYS

    print("\n  Placement Prep Agent — Environment Check")
    print("  " + "─" * 44)

    status = validate_env(raise_on_missing=False)

    all_ok = True
    for key, hint in {**REQUIRED_KEYS, **OPTIONAL_KEYS}.items():
        ok  = status.get(key, False)
        req = key in REQUIRED_KEYS
        tag = "✓" if ok else ("✗ REQUIRED" if req else "○ optional")
        val = os.getenv(key, "")
        masked = (val[:6] + "••••") if val else "not set"
        print(f"  {tag:<12} {key:<26} {masked}")
        if req and not ok:
            all_ok = False

    print()
    if all_ok:
        print("  ✓ All required keys set. Agent is ready.\n")
    else:
        print("  ✗ Set missing keys in your .env file, then re-run.\n")
        sys.exit(1)


def cmd_research(args):
    """Run a research session in the terminal."""
    from src.utils import validate_env, gemini, search, \
        extract_questions, build_metadata, truncate

    validate_env()   # raises if keys missing

    company = args.company
    role    = args.role
    focus   = args.focus
    n_q     = args.questions

    print(f"\n  Placement Prep Agent")
    print(f"  {'─' * 40}")
    print(f"  Company : {company}")
    print(f"  Role    : {role}")
    print(f"  Focus   : {focus}")
    print()

    # ── Step 1: Company metadata ──────────────────────────────
    print("  [1/4] Fetching company info…")
    try:
        snippets = search(f"{company} founded headquarters industry type", max_results=3)
        raw      = gemini(
            f"From the text below, reply EXACTLY in this format:\n"
            f"Founded: <year>\nHQ: <city>\nType: <MNC/Startup/Product/Service>\n\n"
            f"Text: {truncate(' '.join(snippets), 1500)}"
        )
        meta = build_metadata(raw)
    except Exception as e:
        meta = {"founded": "?", "hq": "?", "type": "?"}
        print(f"  ⚠ metadata error: {e}")

    print(f"     Founded: {meta['founded']}  |  HQ: {meta['hq']}  |  Type: {meta['type']}")

    # ── Step 2: Research ─────────────────────────────────────
    print(f"  [2/4] Searching interview experiences…")
    try:
        snippets = search(f"{company} {role} interview {focus} experience 2024 2025")
        print(f"     {len(snippets)} snippets collected")
    except Exception as e:
        snippets = []
        print(f"  ⚠ search error: {e}")

    # ── Step 3: Synthesis ────────────────────────────────────
    print(f"  [3/4] Synthesising with Gemini…")
    try:
        block     = "\n---\n".join(snippets)
        synthesis = gemini(
            f"Summarise the {company} {role} interview process for {focus} in 120 words.\n"
            f"Founded {meta['founded']}, HQ {meta['hq']}.\n\n{truncate(block, 3000)}"
        )
    except Exception as e:
        synthesis = f"Could not synthesise: {e}"

    # ── Step 4: Questions ────────────────────────────────────
    print(f"  [4/4] Generating {n_q} questions…")
    try:
        raw_qs    = gemini(
            f"Generate exactly {n_q} {focus} interview questions for {company} {role}.\n"
            f"Format: Q1. <question> [Easy/Medium/Hard]\n"
            f"Context: {truncate(synthesis, 400)}"
        )
        questions = extract_questions(raw_qs)
    except Exception as e:
        questions = [f"Error: {e}"]

    # ── Output ───────────────────────────────────────────────
    print(f"\n  {'═' * 50}")
    print(f"  {company} — {role} Interview Prep")
    print(f"  {'═' * 50}")
    print(f"\n  SUMMARY\n  {'─' * 40}")
    print(f"  {synthesis}\n")
    print(f"  {focus.upper()} QUESTIONS\n  {'─' * 40}")
    for q in questions:
        print(f"  {q}")
    print()


def cmd_ui(args):
    """Launch the Streamlit web UI."""
    app = ROOT / "week5" / "day34_35_app.py"
    if not app.exists():
        print(f"  ✗ App not found: {app}")
        sys.exit(1)
    print(f"  Launching Streamlit UI…")
    print(f"  Open: http://localhost:8501\n")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app)],
        cwd=ROOT,
    )


def cmd_test(args):
    """Run the full test suite."""
    print("  Running test suite…\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "week6/day37_unit_tests.py",
         "week6/day38_integration_tests.py",
         "-v", "--tb=short"],
        cwd=ROOT,
    )
    sys.exit(result.returncode)


# ═══════════════════════════════════════════════════════════════
#  CLI PARSER
# ═══════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="placement-prep",
        description="Placement Prep Agent — research companies, generate questions, launch UI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py env
  python main.py research --company Google --role SDE-2 --focus DSA
  python main.py research --company Flipkart --role PM --focus Behavioral --questions 3
  python main.py ui
  python main.py test
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # env
    sub.add_parser("env", help="Validate .env and print key status")

    # research
    r = sub.add_parser("research", help="Run a research session in the terminal")
    r.add_argument("--company",   required=True,  help="Company name, e.g. Google")
    r.add_argument("--role",      required=True,  help="Job role, e.g. SDE-2")
    r.add_argument("--focus",     default="DSA",
                   choices=["DSA", "System Design", "Behavioral", "SQL", "Low-Level Design"],
                   help="Interview focus area (default: DSA)")
    r.add_argument("--questions", type=int, default=5, metavar="N",
                   help="Number of questions to generate (default: 5)")

    # ui
    sub.add_parser("ui", help="Launch the Streamlit web UI")

    # test
    sub.add_parser("test", help="Run the full test suite (pytest)")

    return p


def main():
    parser  = build_parser()
    args    = parser.parse_args()
    dispatch = {
        "env":      cmd_env,
        "research": cmd_research,
        "ui":       cmd_ui,
        "test":     cmd_test,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
