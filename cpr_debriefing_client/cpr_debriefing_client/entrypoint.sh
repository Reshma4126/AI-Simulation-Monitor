#!/bin/sh
# entrypoint.sh — waits for Ollama, pulls the model, then starts Flask
set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5:0.5b}"

echo "============================================================"
echo "  CPR Debriefing System"
echo "  Ollama host : $OLLAMA_HOST"
echo "  Model       : $MODEL"
echo "============================================================"

# ── Wait for Ollama to be reachable ──────────────────────────────────────────
echo "[startup] Waiting for Ollama to be ready..."
MAX_WAIT=120
WAITED=0
until curl -sf "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "[startup] ERROR: Ollama did not start within ${MAX_WAIT}s. Continuing anyway..."
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo "[startup]   still waiting... (${WAITED}s)"
done
echo "[startup] Ollama is up."

# ── Pull model if not already cached ─────────────────────────────────────────
echo "[startup] Ensuring model '$MODEL' is available..."
curl -sf -X POST "$OLLAMA_HOST/api/pull" \
     -H "Content-Type: application/json" \
     -d "{\"name\": \"$MODEL\"}" \
     | tail -1 || echo "[startup] Model pull returned non-zero (may already be cached)."
echo "[startup] Model ready."

# ── Launch Flask via Gunicorn ─────────────────────────────────────────────────
echo "[startup] Starting Flask server on :5000 ..."
exec gunicorn server:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 180 \
    --keep-alive 5 \
    --log-level info
