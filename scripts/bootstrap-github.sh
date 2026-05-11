#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-alien-kai}"
REPO="${2:-ai-agent-delivery-pipeline}"
VISIBILITY="${3:-private}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required. Install it and run: gh auth login"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run: gh auth login"
  exit 1
fi

if [ "$VISIBILITY" != "private" ] && [ "$VISIBILITY" != "public" ]; then
  echo "Visibility must be private or public."
  exit 1
fi

if [ ! -d .git ]; then
  git init
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Initial AI agent delivery pipeline scaffold"
fi

if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "Repository $OWNER/$REPO already exists."
else
  gh repo create "$OWNER/$REPO" --"$VISIBILITY" --description "AI agent delivery pipeline: GitHub + Claude Code Routine + Codex" --source=. --remote=origin --push
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "https://github.com/$OWNER/$REPO.git"
fi

git branch -M main
git push -u origin main

echo "Repository is ready: https://github.com/$OWNER/$REPO"
echo "Next: run ./scripts/create-labels.sh and add ROUTINE_FIRE_URL / ROUTINE_FIRE_TOKEN to GitHub Secrets."
