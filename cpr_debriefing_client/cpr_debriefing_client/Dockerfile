# =============================================================================
# CPR Debriefing System — Dockerfile
# Single-stage build: Python 3.11 runtime.
# The React frontend is pre-built (client/dist/) before this image is built,
# so no Node.js is needed here — just copy the dist folder.
# =============================================================================

FROM python:3.11-slim

# System libraries needed by audio processing packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install PyTorch CPU (explicit wheel to avoid a 2 GB CUDA download) ────────
RUN pip install --no-cache-dir \
        torch==2.5.1+cpu \
        torchaudio==2.5.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu

# ── Install all Python dependencies ───────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Download spaCy model via direct wheel (avoids CLI URL generation bug) ─────
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# ── Copy application code ─────────────────────────────────────────────────────
COPY . .

# ── Runtime directories ───────────────────────────────────────────────────────
RUN mkdir -p uploads output/reports output/tts logs data/sessions

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
