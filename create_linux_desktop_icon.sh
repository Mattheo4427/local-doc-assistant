#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
LAUNCHER_PATH="$DESKTOP_DIR/Local-Document-Assistant.desktop"

mkdir -p "$DESKTOP_DIR"

cat > "$LAUNCHER_PATH" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Local Document Assistant
Comment=Launch local GPT-style document assistant
Exec=bash -lc "cd \"$SCRIPT_DIR\" && ./run_app.sh"
Path=$SCRIPT_DIR
Terminal=true
Categories=Utility;Development;
EOF

chmod +x "$LAUNCHER_PATH"

printf "Desktop launcher created at: %s\n" "$LAUNCHER_PATH"
printf "If your desktop asks, mark it as trusted before first run.\n"
