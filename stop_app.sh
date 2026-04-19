#!/usr/bin/env bash
set -euo pipefail

docker stop open-webui-local >/dev/null 2>&1 || true
echo "Open WebUI stopped (if it was running)."
