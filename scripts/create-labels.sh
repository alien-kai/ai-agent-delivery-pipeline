#!/usr/bin/env bash
set -euo pipefail

create_label() {
  local name="$1"
  local color="$2"
  local desc="$3"

  if gh label list --limit 200 | awk -F'\t' '{print $1}' | grep -Fxq "$name"; then
    gh label edit "$name" --color "$color" --description "$desc" >/dev/null
  else
    gh label create "$name" --color "$color" --description "$desc" >/dev/null
  fi
}

create_label "ai:plan" "0E8A16" "AI planner entrypoint"
create_label "ai:planned" "5319E7" "Task spec generated"
create_label "ai:ready-for-codex" "1D76DB" "Ready for Codex execution"
create_label "ai:implementing" "FBCA04" "Codex is implementing"
create_label "ai:review" "C5DEF5" "AI review required"
create_label "ai:ci-failed" "B60205" "CI failed, AI fix required"
create_label "ai:auto-merge-eligible" "0E8A16" "Green lane auto merge eligible"
create_label "ai:human-required" "D93F0B" "Human approval required"

create_label "risk:green" "0E8A16" "Low risk"
create_label "risk:yellow" "FBCA04" "Medium risk"
create_label "risk:red" "B60205" "High risk"
create_label "risk:unknown" "BDBDBD" "Unknown risk"

echo "Labels are ready."
