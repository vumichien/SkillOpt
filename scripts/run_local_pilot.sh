#!/usr/bin/env bash
# Launch the mcqa local pilot: DeepSeek optimizer (cloud) + local Qwen2.5-7B target (Ollama).
# Resume-aware: re-running continues the same outputs/mcqa_local_pilot run.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 1. Load .env.local-pilot if present
ENV_FILE="$PROJECT_ROOT/.env.local-pilot"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  echo "[pilot] loaded $ENV_FILE"
else
  echo "[pilot] no .env.local-pilot found; relying on current environment"
fi

# 2. Fail fast if the DeepSeek optimizer key is missing
if [ -z "${OPTIMIZER_OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPTIMIZER_OPENAI_API_KEY is not set. Copy .env.local-pilot.example to .env.local-pilot and fill it in." >&2
  exit 1
fi

# 3. Ensure Ollama is up and the target model is pulled
MODEL="${TARGET_DEPLOYMENT:-qwen2.5:7b-instruct-q4_K_M}"
OLLAMA_BASE="${QWEN_CHAT_BASE_URL:-http://localhost:11434/v1}"
if ! curl -sf "$OLLAMA_BASE/models" >/dev/null 2>&1; then
  echo "ERROR: Ollama not reachable at $OLLAMA_BASE. Start it with 'ollama serve'." >&2
  exit 1
fi
if ! ollama list 2>/dev/null | grep -qF "$MODEL"; then
  echo "[pilot] pulling $MODEL ..."
  ollama pull "$MODEL"
fi

# 4. Run training (PYTHONUTF8 guards config loading on non-UTF8 locales)
export PYTHONUTF8=1
OUT_ROOT="outputs/mcqa_local_pilot"
if [ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]; then
  PY="$PROJECT_ROOT/.venv/Scripts/python.exe"
elif [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PY="$PROJECT_ROOT/.venv/bin/python"
else
  PY="python"
fi
echo "[pilot] optimizer=deepseek-chat  target=$MODEL  out_root=$OUT_ROOT"
"$PY" scripts/train.py --config configs/mcqa/local-pilot.yaml --out_root "$OUT_ROOT"
echo "[pilot] done. Artifacts in $OUT_ROOT (best_skill.md, history.json, skills/)"
