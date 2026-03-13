#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${SKILOAD_BASE_URL:-https://skiload.com}"
BIN_DIR="${SKILOAD_BIN_DIR:-$HOME/.local/bin}"
CLI_PATH="$BIN_DIR/skiload"
CLI_URL="$BASE_URL/install/skiload-cli.py"
STORE_SKILL_URL="$BASE_URL/install/store-skill.md"
CLI_ONLY=0

usage() {
  cat <<'EOF'
Usage: install.sh [--cli-only]

Options:
  --cli-only   Install only the skiload CLI
  -h, --help   Show this help
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

install_store_skill() {
  local skills_root="$1"
  local target_dir="$skills_root/skiload-store"
  local target_file="$target_dir/SKILL.md"

  mkdir -p "$target_dir"
  curl -fsSL "$STORE_SKILL_URL" -o "$target_file"
  echo "Installed store skill to $target_file"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --cli-only)
      CLI_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

require_cmd curl
require_cmd python3

mkdir -p "$BIN_DIR"
curl -fsSL "$CLI_URL" -o "$CLI_PATH"
chmod +x "$CLI_PATH"
echo "Installed skiload CLI to $CLI_PATH"

if [ "$CLI_ONLY" -eq 0 ]; then
  install_store_skill "${CODEX_HOME:-$HOME/.codex}/skills"

  if [ -d "$HOME/.claude" ] || [ -d "$HOME/.claude/skills" ]; then
    install_store_skill "$HOME/.claude/skills"
  fi
fi

if ! echo ":$PATH:" | grep -q ":$BIN_DIR:"; then
  echo "Warning: $BIN_DIR is not in PATH. Add it before using skiload." >&2
fi

echo
echo "Done."
echo "Try: skiload search terminal"
if [ "$CLI_ONLY" -eq 0 ]; then
  echo "Restart your Agent so the Skiload Store skill can be loaded."
fi
