# ─────────────────────────────────────────────────────────────
#  Placement Prep Agent — Production Dockerfile  (Day 43)
#
#  Multi-stage build:
#    Stage 1 (builder) — install deps into a venv, no cache in final image
#    Stage 2 (runtime) — copy venv only, run as non-root user
#
#  Build:   docker build -t placement-prep .
#  Run:     docker run -p 8501:8501 --env-file .env placement-prep
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker layer-caches this step.
# If requirements.txt doesn't change, pip install is skipped on rebuild.
COPY requirements.txt .

# Create venv and install deps into it (isolated from system Python)
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip --quiet && \
    /opt/venv/bin/pip install -r requirements.txt --quiet

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy only the venv from builder — no build tools in final image
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser . .

# Make venv the active Python environment
# Streamlit config via env vars (no config.toml needed at runtime)
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

USER appuser

EXPOSE 8501

# Health check — Streamlit responds on /_stcore/health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "week5/day34_35_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
