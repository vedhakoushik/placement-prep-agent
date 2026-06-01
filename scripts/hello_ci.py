"""
hello_ci.py — the 'small thing' our learning workflow calls.
Prints a greeting + the time + how many .py files are in the repo.
Run locally:  python scripts/hello_ci.py
"""

import datetime
import os


def count_py_files(root: str = ".") -> int:
    total = 0
    for dirpath, _, files in os.walk(root):
        if ".git" in dirpath or ".venv" in dirpath:
            continue
        total += sum(1 for f in files if f.endswith(".py"))
    return total


if __name__ == "__main__":
    print("=" * 50)
    print("  Hello from GitHub Actions!")
    print("=" * 50)
    print(f"  Time (UTC): {datetime.datetime.utcnow().isoformat(timespec='seconds')}")
    print(f"  Python files in repo: {count_py_files()}")
    print(f"  Runner OS: {os.getenv('RUNNER_OS', 'local machine')}")
    print("=" * 50)
    print("  Workflow ran successfully [OK]")
