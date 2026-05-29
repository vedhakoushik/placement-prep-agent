"""
Day 43-44 -- Docker & Docker Compose
======================================
TWO phases:

Phase 1 (Day 43) — Single container
  Build a production-ready image for the Streamlit app.
  ONE concept: a Docker image is a portable, reproducible snapshot of your
  entire app — code + Python + deps + config — that runs identically on
  your laptop, CI, and a cloud server.

  Key ideas:
    Multi-stage build     → builder installs deps; runtime stage is lean (~400 MB vs 900 MB)
    Non-root user         → security: never run as root in production
    Layer caching         → COPY requirements.txt first → pip install is cached
    HEALTHCHECK           → Docker auto-restarts the container if app stops responding
    .dockerignore         → keeps .env, .venv, __pycache__ out of the image

Phase 2 (Day 44) — Two containers with Compose
  Add ChromaDB as a separate service. Compose wires them together.
  THREE concepts:

  1. VOLUMES
     Named Docker volumes persist database data across container restarts.
     `docker compose down` stops containers but keeps the data.
     `docker compose down -v` wipes it.

  2. ENVIRONMENT
     API keys from .env are injected via `env_file` — they are never
     hardcoded in the Compose file and never copied into the image.
     Docker-specific config (CHROMA_HOST, IS_PERSISTENT) goes under
     `environment` and is always set regardless of .env.

  3. DEPENDS_ON
     `condition: service_healthy` makes Docker wait until ChromaDB's
     healthcheck returns 200 before starting Streamlit.
     Without it: Streamlit starts, tries to connect to ChromaDB,
     gets "connection refused", crashes.

Files:
  Dockerfile          — multi-stage production build
  docker-compose.yml  — two-service orchestration
  .dockerignore       — excludes .env, .venv, __pycache__
  .env.example        — API key template (committed; .env is gitignored)
  src/chroma_client.py — smart client: HttpClient in Docker, PersistentClient locally

Run:
  python week7/day43_44_docker.py   # prints this summary + validates setup
  docker compose up --build         # build + start both containers
  docker compose down               # stop (data survives in named volume)
  docker compose down -v            # stop + wipe all volumes

Interview talking points at the bottom of this file.
"""

import io
import os
import sys
import subprocess
from pathlib import Path

# Force UTF-8 output on Windows (avoids UnicodeEncodeError for box-drawing chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════
#  PHASE 1 CONCEPTS — Single container
# ═══════════════════════════════════════════════════════════════

DOCKERFILE_ANATOMY = """
  Dockerfile walkthrough (multi-stage)
  ─────────────────────────────────────

  Stage 1 — builder
  ──────────────────
  FROM python:3.11-slim AS builder
  │  Start from official image, alias this stage "builder"
  │
  COPY requirements.txt .
  RUN python -m venv /opt/venv && pip install -r requirements.txt
  │  COPY requirements FIRST — if it hasn't changed, Docker skips
  │  the pip install entirely (layer cache hit). Big speed win.

  Stage 2 — runtime                     ← fresh image, no build tools
  ──────────────────────────────────────
  FROM python:3.11-slim AS runtime
  │
  COPY --from=builder /opt/venv /opt/venv
  │  Copy ONLY the venv. gcc, make, build-essential stay behind.
  │  Final image = ~400 MB instead of ~900 MB.
  │
  RUN useradd appuser && USER appuser
  │  Never run as root. If the app is compromised, attacker has
  │  only appuser's permissions, not full system access.
  │
  HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health
  │  Docker checks every 30s. Fails → container auto-restarts.
  │
  CMD ["streamlit", "run", "week5/day34_35_app.py"]
     Default command. Can be overridden at `docker run` time.
"""

LAYER_CACHING = """
  Layer caching — why COPY order matters
  ────────────────────────────────────────

  SLOW (source changes → pip reinstalls every time):
    COPY . .
    RUN pip install -r requirements.txt

  FAST (requirements rarely change → pip is cached):
    COPY requirements.txt .       ← only this file
    RUN pip install ...           ← cached unless requirements changed
    COPY . .                      ← all source (changes often, but pip is done)

  Rule: put what changes LEAST at the TOP of the Dockerfile.
"""


# ═══════════════════════════════════════════════════════════════
#  PHASE 2 CONCEPTS — Two containers with Compose
# ═══════════════════════════════════════════════════════════════

VOLUMES_EXPLAINED = """
  CONCEPT 1: Volumes — data that survives container restarts
  ──────────────────────────────────────────────────────────

  Two types of mounts in docker-compose.yml:

  Named volume (for databases):
    volumes:
      - chroma_data:/chroma/chroma   ← Docker manages the location

    docker compose down      → containers removed, chroma_data KEPT
    docker compose down -v   → containers AND chroma_data REMOVED
    docker compose up        → ChromaDB reloads the saved data

  Bind mount (for development):
    volumes:
      - .:/app                       ← you control the path (your folder)

    Edit code on your machine → changes appear inside the container immediately.
    Used for Streamlit live reload. NOT for databases (folder deletion = data loss).

  Named volume location on disk:
    Linux/Mac:  /var/lib/docker/volumes/chroma_data/_data
    Windows:    inside the Docker Desktop WSL2 virtual disk
"""

ENVIRONMENT_EXPLAINED = """
  CONCEPT 2: Environment — secrets without hardcoding
  ────────────────────────────────────────────────────

  Three layers in docker-compose.yml:

  1. env_file (secrets — from .env, never committed):
       env_file:
         - .env
     Reads GEMINI_API_KEY, TAVILY_API_KEY etc. from your .env file.
     The file is read at runtime — never copied into the image.

  2. environment (Docker-specific config — safe to commit):
       environment:
         - CHROMA_HOST=chromadb     ← tells app to use HttpClient
         - CHROMA_PORT=8000
         - STREAMLIT_SERVER_HEADLESS=true
     Always set, regardless of what's in .env. No secrets here.

  3. Image ENV (build-time defaults — in Dockerfile):
       ENV PATH="/opt/venv/bin:$PATH" \\
           PYTHONUNBUFFERED=1
     Baked into the image. Never put secrets here — they appear in
     `docker inspect` and image layers.

  Rule: secrets → .env + env_file | config → environment | defaults → Dockerfile ENV
"""

DEPENDS_ON_EXPLAINED = """
  CONCEPT 3: depends_on — wait for the dependency to be ready
  ─────────────────────────────────────────────────────────────

  Basic (waits for container to START — not enough for databases):
    depends_on:
      - chromadb

  With health check (waits for container to be HEALTHY):
    depends_on:
      chromadb:
        condition: service_healthy

  healthcheck in the chromadb service:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 10s

  Timeline:
    0s   docker compose up
    1s   chromadb container starts, ChromaDB server boots
    8s   first health check → ChromaDB not ready yet (retrying)
   12s   second health check → returns 200 → service_healthy
   12s   app container starts (Streamlit)
   27s   Streamlit ready at http://localhost:8501

  Without depends_on: app starts immediately, can't reach ChromaDB → crash.
"""

INTERNAL_NETWORK = """
  Internal network — how services talk to each other
  ───────────────────────────────────────────────────

  docker-compose.yml defines a named network:
    networks:
      placement-net:
        driver: bridge

  Both services join it:
    chromadb:
      networks: [placement-net]
    app:
      networks: [placement-net]

  Docker registers each service name as a hostname on that network.
  From inside the app container:
    http://chromadb:8000   → reaches the chromadb container
    http://app:8501        → reaches itself

  Port 8000 is still exposed to the host (so local week3/ scripts can
  connect directly). But the app→chromadb connection goes through the
  internal network — no internet, no NAT, very fast.
"""

COMPOSE_COMMANDS = """
  Compose command reference
  ──────────────────────────
  docker compose up                # start all services (build if needed)
  docker compose up --build        # force rebuild of app image
  docker compose up -d             # start in background (detached)
  docker compose down              # stop + remove containers (data survives)
  docker compose down -v           # stop + remove containers + wipe volumes
  docker compose ps                # show status of each service
  docker compose logs -f           # tail all logs
  docker compose logs app          # logs from one service only
  docker compose exec app bash     # open a shell inside the app container
  docker compose exec chromadb sh  # open a shell inside chromadb container
"""


# ═══════════════════════════════════════════════════════════════
#  INTERVIEW Q&A
# ═══════════════════════════════════════════════════════════════

INTERVIEW_QA = [
    ("What is a Docker volume and why do you need one?",
     "A named volume is storage Docker manages outside the container filesystem. "
     "Data written to it survives `docker compose down`. Without it, every restart "
     "wipes the database — ChromaDB would lose all vectors on every redeploy."),

    ("How do you pass API keys to a Docker container without hardcoding them?",
     "Use `env_file: .env` in docker-compose.yml. Docker reads each KEY=VALUE from "
     ".env and injects it as an environment variable. The file never enters the image. "
     "The .env file is gitignored — contributors copy .env.example and fill in their keys."),

    ("What does depends_on condition: service_healthy do?",
     "It makes Docker wait until the dependency passes its healthcheck before starting "
     "the dependent container. Basic depends_on only waits for the container to start, "
     "not for the process inside it to be ready. Databases need service_healthy because "
     "they take a few seconds to open their port after the container starts."),

    ("How do two Docker containers communicate with each other?",
     "They join the same Docker network. Compose creates one automatically, or you "
     "define a named one. Docker registers each service name as a hostname on that "
     "network — the app reaches ChromaDB at http://chromadb:8000 without knowing "
     "any IP addresses. Traffic stays inside the Docker host; no internet involved."),

    ("What is the difference between a named volume and a bind mount?",
     "Named volume: Docker manages the location. Good for databases — data persists "
     "and you can't accidentally delete it. "
     "Bind mount: you specify the path (e.g. .:/app). Good for development — "
     "code changes on your host appear inside the container immediately for live reload. "
     "Don't use bind mounts for database storage."),

    ("Why use a multi-stage Dockerfile?",
     "To keep the final image small and free of build tools. Stage 1 (builder) "
     "installs gcc, pip, and all packages. Stage 2 (runtime) starts fresh and copies "
     "only the built venv. The 500 MB of build tools never end up in production. "
     "Smaller image = faster pulls, smaller attack surface."),

    ("What happens when you run docker compose down?",
     "Containers are stopped and removed. Named volumes (chroma_data) are kept — "
     "the database data survives. Images are kept. `docker compose up` brings "
     "everything back with the same data. To also wipe volumes, run `down -v`."),
]


# ═══════════════════════════════════════════════════════════════
#  VALIDATORS
# ═══════════════════════════════════════════════════════════════

def validate_files():
    print("\n  File checklist")
    print("  " + "─" * 46)

    files = {
        "Dockerfile":            "multi-stage production build",
        "docker-compose.yml":    "two-service orchestration (app + chromadb)",
        ".dockerignore":         "excludes .env, .venv, __pycache__",
        ".env.example":          "API key template (committed; .env is gitignored)",
        "src/chroma_client.py":  "HttpClient in Docker, PersistentClient locally",
    }

    all_ok = True
    for filename, desc in files.items():
        path   = ROOT / filename
        exists = path.exists()
        mark   = "✓" if exists else "✗"
        print(f"  {mark}  {filename:<28} {desc}")
        if not exists:
            all_ok = False

    return all_ok


def validate_compose():
    """Check that docker-compose.yml has all three concepts."""
    print("\n  docker-compose.yml concept check")
    print("  " + "─" * 46)

    path = ROOT / "docker-compose.yml"
    if not path.exists():
        print("  ✗  docker-compose.yml not found")
        return False

    text = path.read_text(encoding="utf-8")
    checks = [
        ("chroma_data:",            "Named volume defined"),
        ("volumes:",                "Volume mount configured"),
        ("env_file:",               "env_file (secrets from .env)"),
        ("CHROMA_HOST=chromadb",    "CHROMA_HOST injected for inter-service talk"),
        ("condition: service_healthy", "depends_on with health check"),
        ("placement-net:",          "Explicit named network"),
        ("driver: bridge",          "Bridge network driver"),
    ]

    all_ok = True
    for needle, label in checks:
        found = needle in text
        mark  = "✓" if found else "✗"
        print(f"  {mark}  {label}")
        if not found:
            all_ok = False

    return all_ok


def check_docker():
    print("\n  Docker installation")
    print("  " + "─" * 46)
    try:
        out = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            print(f"  ✓  {out.stdout.strip()}")

            # Also check compose
            comp = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5
            )
            if comp.returncode == 0:
                print(f"  ✓  {comp.stdout.strip()}")
            return True
        print("  ✗  Docker not responding")
        return False
    except FileNotFoundError:
        print("  ✗  Docker not installed — https://docker.com")
        return False


def show_commands():
    print("\n  Commands to run")
    print("  " + "─" * 46)
    cmds = [
        ("Start everything",   "docker compose up --build"),
        ("Start in background","docker compose up -d --build"),
        ("Check status",       "docker compose ps"),
        ("Tail logs",          "docker compose logs -f"),
        ("Stop (keep data)",   "docker compose down"),
        ("Stop + wipe data",   "docker compose down -v"),
        ("Shell in app",       "docker compose exec app bash"),
        ("Shell in chromadb",  "docker compose exec chromadb sh"),
    ]
    for label, cmd in cmds:
        print(f"  {label:<22}  {cmd}")


def show_interview_qa():
    print("\n  Interview Q&A")
    print("  " + "─" * 46)
    for i, (q, a) in enumerate(INTERVIEW_QA, 1):
        print(f"\n  Q{i}: {q}")
        print(f"   A: {a}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 58)
    print("  Day 43-44 -- Docker & Docker Compose")
    print("  Phase 1: single container | Phase 2: two containers")
    print("=" * 58)

    print(DOCKERFILE_ANATOMY)
    print(LAYER_CACHING)

    print("\n" + "─" * 58)
    print("  Phase 2 — Three Compose concepts")
    print("─" * 58)
    print(VOLUMES_EXPLAINED)
    print(ENVIRONMENT_EXPLAINED)
    print(DEPENDS_ON_EXPLAINED)
    print(INTERNAL_NETWORK)
    print(COMPOSE_COMMANDS)

    files_ok   = validate_files()
    compose_ok = validate_compose()
    docker_ok  = check_docker()

    show_commands()
    show_interview_qa()

    print("\n" + "=" * 58)
    print("  Summary")
    print(f"  Files in place:      {'Yes' if files_ok   else 'No — check above'}")
    print(f"  Compose concepts:    {'All present' if compose_ok else 'Missing — check docker-compose.yml'}")
    print(f"  Docker installed:    {'Yes' if docker_ok  else 'No — install Docker Desktop'}")
    print()
    print("  Three rules for Compose:")
    print("  1. Databases need named volumes — not bind mounts")
    print("  2. Secrets go in .env + env_file — never in the Compose file")
    print("  3. Use condition: service_healthy — not just depends_on: [name]")
    print("=" * 58)
