#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="open-webui-local"
IMAGE_NAME="ghcr.io/open-webui/open-webui:main"
HOST_PORT="3000"
DEFAULT_OLLAMA_BASE_URL="http://host.docker.internal:11434"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-$DEFAULT_OLLAMA_BASE_URL}"
WEBUI_AUTH="False"

detect_ollama_endpoint() {
  local candidates=()
  local wsl_nameserver=""

  # User override wins if explicitly set.
  if [[ -n "${OLLAMA_BASE_URL:-}" ]]; then
    candidates+=("$OLLAMA_BASE_URL")
  fi

  # WSL often exposes Windows host as nameserver from resolv.conf.
  if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
    wsl_nameserver="$(awk '/^nameserver / {print $2; exit}' /etc/resolv.conf 2>/dev/null || true)"
    if [[ -n "$wsl_nameserver" ]]; then
      candidates+=("http://${wsl_nameserver}:11434")
    fi
  fi

  candidates+=(
    "$DEFAULT_OLLAMA_BASE_URL"
    "http://localhost:11434"
    "http://172.17.0.1:11434"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 2 "${candidate}/api/tags" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done

  # If none verified, return current configured endpoint as fallback.
  echo "$OLLAMA_BASE_URL"
  return 0
}

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker is required to run Open WebUI."
  echo "Install Docker, start Docker daemon, then retry."
  exit 1
fi

OLLAMA_BASE_URL="$(detect_ollama_endpoint)"
echo "[INFO] Using Ollama endpoint: $OLLAMA_BASE_URL"

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS --max-time 2 "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
    echo "[WARN] Could not verify ${OLLAMA_BASE_URL} from this shell."
    echo "       Open WebUI may launch with 'No models available'."
    echo "       If Ollama runs on Windows, expose it first in PowerShell:"
    echo "         setx OLLAMA_HOST 0.0.0.0:11434"
    echo "       Then restart Ollama and retry."
    echo "       You can also override endpoint per run:"
    echo "         OLLAMA_BASE_URL=http://<windows-host-ip>:11434 bash run_app.sh"
  fi
else
  echo "[WARN] curl not found; skipping Ollama endpoint precheck."
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  CURRENT_URL="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_NAME" 2>/dev/null | grep '^OLLAMA_BASE_URL=' | cut -d= -f2- || true)"
  CURRENT_AUTH="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_NAME" 2>/dev/null | grep '^WEBUI_AUTH=' | cut -d= -f2- || true)"
  if [[ "$CURRENT_URL" != "$OLLAMA_BASE_URL" || "$CURRENT_AUTH" != "$WEBUI_AUTH" ]]; then
    echo "[INFO] Recreating container to apply runtime settings (OLLAMA_BASE_URL / WEBUI_AUTH)."
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "[INFO] Starting existing Open WebUI container..."
  docker start "$CONTAINER_NAME" >/dev/null
else
  echo "[INFO] Creating Open WebUI container..."
  echo "[INFO] Trying image: $IMAGE_NAME"
  if ! docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT":8080 \
    --add-host=host.docker.internal:host-gateway \
    -e OLLAMA_BASE_URL="$OLLAMA_BASE_URL" \
    -e WEBUI_AUTH="$WEBUI_AUTH" \
    -v open-webui:/app/backend/data \
    "$IMAGE_NAME" >/dev/null; then
    echo "[WARN] Initial GHCR pull/start failed. Retrying after docker logout ghcr.io..."
    docker logout ghcr.io >/dev/null 2>&1 || true
    if ! docker run -d \
      --name "$CONTAINER_NAME" \
      -p "$HOST_PORT":8080 \
      --add-host=host.docker.internal:host-gateway \
      -e OLLAMA_BASE_URL="$OLLAMA_BASE_URL" \
      -e WEBUI_AUTH="$WEBUI_AUTH" \
      -v open-webui:/app/backend/data \
      "$IMAGE_NAME" >/dev/null; then
      echo "[ERROR] Could not pull/start Open WebUI image from GHCR."
      echo "Try manually:"
      echo "  docker logout ghcr.io"
      echo "  docker pull ghcr.io/open-webui/open-webui:main"
      exit 1
    fi
  fi
fi

READY_URL="http://localhost:${HOST_PORT}"
echo "[INFO] Waiting for Open WebUI HTTP readiness..."
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "$READY_URL" >/dev/null 2>&1; then
    echo "[RUN] Open WebUI is available at: $READY_URL"
    break
  fi
  sleep 1
done

if ! curl -fsS --max-time 2 "$READY_URL" >/dev/null 2>&1; then
  echo "[WARN] Open WebUI may still be initializing."
  echo "      Try opening $READY_URL in 20-30 seconds."
else
  echo "[INFO] Note: Docker may show container as 'unhealthy' due upstream healthcheck issue."
fi

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$READY_URL" >/dev/null 2>&1 || true
fi
