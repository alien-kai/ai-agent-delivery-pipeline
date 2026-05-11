#!/usr/bin/env bash
set -euo pipefail

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install Codex CLI."
  exit 1
fi

npm install -g @openai/codex
mkdir -p "$HOME/.codex"

cat > "$HOME/.codex/config.toml" <<'EOF'
cli_auth_credentials_store = "file"
EOF

if [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "WARNING: OPENAI_API_KEY is set. Codex may use API billing instead of ChatGPT subscription auth."
fi

echo "Run: codex login"
echo "Then start your GitHub self-hosted runner for this repository."
