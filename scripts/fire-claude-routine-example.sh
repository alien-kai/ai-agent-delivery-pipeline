#!/usr/bin/env bash
set -euo pipefail

: "${ROUTINE_FIRE_URL:?Set ROUTINE_FIRE_URL}"
: "${ROUTINE_FIRE_TOKEN:?Set ROUTINE_FIRE_TOKEN}"

ISSUE_NUMBER="${1:-1}"
ISSUE_TITLE="${2:-Example AI task}"
ISSUE_BODY="${3:-Create a task spec for this example issue.}"
REPO="${4:-alien-kai/ai-agent-delivery-pipeline}"

jq -n \
  --arg issue_number "$ISSUE_NUMBER" \
  --arg issue_title "$ISSUE_TITLE" \
  --arg issue_body "$ISSUE_BODY" \
  --arg repo "$REPO" \
  '{
    text: (
      "GitHub issue planning request\n\n" +
      "repo: " + $repo + "\n" +
      "issue_number: " + $issue_number + "\n" +
      "issue_title: " + $issue_title + "\n\n" +
      "issue_body:\n" + $issue_body
    )
  }' > /tmp/claude-routine-payload.json

curl -X POST "$ROUTINE_FIRE_URL" \
  -H "Authorization: Bearer $ROUTINE_FIRE_TOKEN" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "Content-Type: application/json" \
  --data @/tmp/claude-routine-payload.json
