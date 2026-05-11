#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Run these commands inside Claude Code:

/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup

If Codex CLI is missing, install it locally:

npm install -g @openai/codex
codex login

Smoke test:

/codex:review --background
/codex:status
/codex:result
EOF
