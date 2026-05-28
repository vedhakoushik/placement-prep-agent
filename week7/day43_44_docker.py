"""
Day 43-44 -- Docker
=====================
ONE concept: a Docker image is a portable, reproducible snapshot of your
entire application — code + Python version + dependencies + config — that
runs identically on your laptop, CI, and a cloud server.

What is NEW today:
  1. Multi-stage builds     -- builder stage installs deps; runtime stage is lean
  2. Non-root user          -- security best practice (never run as root)
  3. Layer caching          -- COPY requirements first → pip install cached
  4. HEALTHCHECK directive  -- Docker restarts container if app stops responding
  5. docker-compose.yml     -- local dev with volume mounts for live reload
  6. .dockerignore          -- exclude .env, __pycache__, node_modules from image

Key Docker concepts:
  Image   = snapshot of your app (built once, run anywhere)
  Container = running instance of an image (can have many from one image)
  Layer   = each Dockerfile instruction adds a layer (cached if unchanged)
  Volume  = mount host directory into container (live reload in dev)
  Port    = container port mapped to host port  (-p 8501:8501)

Files created:
  Dockerfile          -- multi-stage production build
  docker-compose.yml  -- local dev orchestration
  .dockerignore       -- excludes secrets and cache
  .env.example        -- template for required env vars

Run:
  python week7/day43_44_docker.py   # prints concept summary + validates setup
  docker build -t placement-prep .
  docker run -p 8501:8501 --env-file .env placement-prep
  # or:
  docker compose up
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  CONCEPT EXPLAINER
# ═══════════════════════════════════════════════════════════════
DOCKERFILE_ANATOMY = """
  Dockerfile walkthrough
  ──────────────────────

  FROM python:3.11-slim AS builder
  │  └─ Start from official Python image (slim = no extras)
  │     AS builder = name this stage "builder"

  RUN python -m venv /opt/venv
  │  └─ Create isolated virtual environment
  │     All packages go here, not into system Python

  COPY requirements.txt .
  RUN pip install -r requirements.txt
  │  └─ COPY first → pip install second
  │     Docker caches the pip install layer as long as
  │     requirements.txt doesn't change. Huge speed win.

  FROM python:3.11-slim AS runtime   ← NEW stage, fresh image
  │  └─ Start over from a clean image
  │     None of the build tools (gcc, make) end up in production

  COPY --from=builder /opt/venv /opt/venv
  │  └─ Copy ONLY the venv from the builder stage
  │     Final image = 400 MB instead of 900 MB

  RUN useradd appuser
  USER appuser
  │  └─ Never run as root in production
  │     If the app is hacked, attacker has limited permissions

  HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health
  │  └─ Docker checks this every 30s
  │     Container auto-restarts if health check fails

  CMD ["streamlit", "run", "week5/day34_35_app.py"]
     └─ Default command when container starts
"""

LAYER_CACHING = """
  Layer caching — why order matters
  ──────────────────────────────────

  Slow (requirements change → reinstall every time):
    COPY . .                        ← copies ALL source code
    RUN pip install -r requirements.txt

  Fast (requirements rarely change):
    COPY requirements.txt .         ← only requirements file
    RUN pip install -r requirements.txt   ← cached unless req changed
    COPY . .                        ← source code (changes often)

  Rule: put things that change LEAST at the TOP.
"""

COMPOSE_VS_RUN = """
  docker run vs docker compose
  ────────────────────────────

  docker run (one-off):
    docker run -p 8501:8501 --env-file .env placement-prep

  docker compose (multi-service, repeatable):
    docker compose up          # reads docker-compose.yml
    docker compose up --build  # rebuild first
    docker compose down        # stop + remove containers
    docker compose logs -f     # tail logs

  Compose benefits:
    - One command starts everything (app + DB + cache)
    - Volume mounts for live reload during development
    - env_file: .env so secrets stay out of compose file
    - restart: unless-stopped for production resilience
"""


# ═══════════════════════════════════════════════════════════════
#  FILE VALIDATOR
# ═══════════════════════════════════════════════════════════════
def validate_docker_files():
    print("\n  Docker file checklist")
    print("  " + "─" * 40)

    files = {
        "Dockerfile":         "Multi-stage production build",
        "docker-compose.yml": "Local dev orchestration",
        ".dockerignore":      "Excludes secrets + cache from image",
        ".env.example":       "API key template for new contributors",
    }

    all_ok = True
    for filename, desc in files.items():
        path = ROOT / filename
        exists = path.exists()
        mark = "✓" if exists else "✗"
        print(f"  {mark}  {filename:<22} {desc}")
        if not exists:
            all_ok = False

    return all_ok


def check_docker_installed():
    print("\n  Docker installation")
    print("  " + "─" * 40)
    try:
        out = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            print(f"  ✓  {out.stdout.strip()}")
            return True
        else:
            print("  ✗  Docker not responding")
            return False
    except FileNotFoundError:
        print("  ✗  Docker not installed — get it at https://docker.com")
        return False
    except Exception as e:
        print(f"  ✗  Error: {e}")
        return False


def show_build_commands():
    print("\n  Next steps — run these commands")
    print("  " + "─" * 40)
    cmds = [
        ("Build image",           "docker build -t placement-prep ."),
        ("Run container",         "docker run -p 8501:8501 --env-file .env placement-prep"),
        ("Or with compose",       "docker compose up"),
        ("Check running",         "docker ps"),
        ("View logs",             "docker logs placement-prep-app"),
        ("Stop compose",          "docker compose down"),
        ("Image size",            "docker image ls placement-prep"),
    ]
    for label, cmd in cmds:
        print(f"  {label:<22}  {cmd}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 58)
    print("  Day 43-44 -- Docker")
    print("  NEW: multi-stage build, non-root user, layer caching")
    print("=" * 58)

    print(DOCKERFILE_ANATOMY)
    print(LAYER_CACHING)
    print(COMPOSE_VS_RUN)

    files_ok  = validate_docker_files()
    docker_ok = check_docker_installed()

    show_build_commands()

    print("\n" + "=" * 58)
    print("  Summary")
    print("  Files in place:    ", "Yes" if files_ok  else "No — check ROOT")
    print("  Docker installed:  ", "Yes" if docker_ok else "No — install Docker Desktop")
    print()
    print("  Key rule: COPY requirements.txt → RUN pip → COPY . .")
    print("  Key rule: multi-stage = lean final image (no build tools)")
    print("  Key rule: never run as root, never bake .env into image")
    print("=" * 58)
