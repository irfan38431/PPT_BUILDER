# ──────────────────────────────────────────────────────────────
# Dockerfile — PPT Builder (Streamlit on Cloud Run)
# Multi-stage build for smaller final image
# ──────────────────────────────────────────────────────────────

# ── Stage 1: Install dependencies ─────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for python-pptx and matplotlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime image ────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Matplotlib needs a writable config dir + font cache
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV FONTCONFIG_FILE=/etc/fonts/fonts.conf

# Runtime system deps (fonts for matplotlib/pptx rendering)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fontconfig \
        libxml2 \
        libxslt1.1 && \
    rm -rf /var/lib/apt/lists/* && \
    fc-cache -f

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create data directories (ephemeral on Cloud Run, but needed at startup)
RUN mkdir -p data/output data/logs data/cache

# Streamlit config: disable CORS/XSRF for Cloud Run proxy, set port
RUN mkdir -p /root/.streamlit && \
    printf '[server]\nport = 8501\nenableCORS = false\nenableXsrfProtection = false\nheadless = true\n\n[browser]\ngatherUsageStats = false\n' \
    > /root/.streamlit/config.toml

EXPOSE 8501

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Run Streamlit
ENTRYPOINT ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
