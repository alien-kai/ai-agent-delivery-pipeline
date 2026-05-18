#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/create-labels.sh
#   ./scripts/create-labels.sh alien-kai ai-agent-delivery-pipeline
#   ./scripts/create-labels.sh alien-kai/ai-agent-delivery-pipeline

detect_repo() {
  if [ "$#" -eq 2 ]; then
    OWNER="$1"
    REPO="$2"
    return
  fi

  if [ "$#" -eq 1 ]; then
    OWNER="${1%/*}"
    REPO="${1#*/}"
    return
  fi

  remote="$(git config --get remote.origin.url || true)"

  if [ -z "$remote" ]; then
    echo "ERROR: Cannot detect GitHub repo. Run:"
    echo "  ./scripts/create-labels.sh alien-kai ai-agent-delivery-pipeline"
    exit 1
  fi

  case "$remote" in
    git@github.com:*)
      full="${remote#git@github.com:}"
      ;;
    https://github.com/*)
      full="${remote#https://github.com/}"
      ;;
    *)
      echo "ERROR: Unsupported remote URL: $remote"
      echo "Run explicitly:"
      echo "  ./scripts/create-labels.sh alien-kai ai-agent-delivery-pipeline"
      exit 1
      ;;
  esac

  full="${full%.git}"
  OWNER="${full%/*}"
  REPO="${full#*/}"
}

urlencode() {
  python3 -c 'import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

create_or_update_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  local encoded
  encoded="$(urlencode "$name")"

  if gh api "repos/${OWNER}/${REPO}/labels/${encoded}" >/dev/null 2>&1; then
    gh api \
      -X PATCH "repos/${OWNER}/${REPO}/labels/${encoded}" \
      -f new_name="$name" \
      -f color="$color" \
      -f description="$description" \
      >/dev/null
    echo "Updated label: $name"
  else
    gh api \
      -X POST "repos/${OWNER}/${REPO}/labels" \
      -f name="$name" \
      -f color="$color" \
      -f description="$description" \
      >/dev/null
    echo "Created label: $name"
  fi
}

detect_repo "$@"

echo "Creating/updating labels for ${OWNER}/${REPO}"

# --- AI lifecycle labels ----------------------------------------------------
create_or_update_label "ai:plan" "0E8A16" "AI planner entrypoint"
create_or_update_label "ai:planned" "5319E7" "Task spec generated"
create_or_update_label "ai:ready-for-codex" "1D76DB" "Ready for Codex execution"
create_or_update_label "ai:implementing" "FBCA04" "Codex is implementing"
create_or_update_label "ai:review" "C5DEF5" "AI review required"
create_or_update_label "ai:needs-fix" "D93F0B" "AI-generated PR needs fix"
create_or_update_label "ai:fixing" "FBCA04" "Codex is applying a bounded auto-fix"
create_or_update_label "ai:ci-failed" "B60205" "CI failed, AI fix required"
create_or_update_label "ai:auto-merge-eligible" "0E8A16" "Green lane auto merge eligible"
create_or_update_label "ai:human-required" "D93F0B" "Human approval required"
create_or_update_label "ai:max-iterations-reached" "B60205" "Auto-fix budget exhausted; human review required"

# --- Risk classification labels --------------------------------------------
# risk:unknown is diagnostic: it flags a PR whose risk classification is
# missing or invalid. The task-spec contract still rejects unknown as a
# valid risk_level value — this label exists only to surface the gap.
create_or_update_label "risk:green" "0E8A16" "Low risk"
create_or_update_label "risk:yellow" "FBCA04" "Medium risk"
create_or_update_label "risk:red" "B60205" "High risk"
create_or_update_label "risk:unknown" "BFDADC" "Risk classification missing or invalid (diagnostic)"

# --- Bounded fix-iteration counters ----------------------------------------
# ai:iter-0 marks the initial implementation / first review. ai:iter-N for
# N>=1 marks the Nth bounded fix iteration. The cap matches the task-spec
# contract's max_iterations bound (0..5) — keep this range in sync if the
# schema is ever widened.
create_or_update_label "ai:iter-0" "C5DEF5" "Initial implementation / first review"
create_or_update_label "ai:iter-1" "C5DEF5" "Bounded fix iteration 1"
create_or_update_label "ai:iter-2" "C5DEF5" "Bounded fix iteration 2"
create_or_update_label "ai:iter-3" "C5DEF5" "Bounded fix iteration 3"
create_or_update_label "ai:iter-4" "C5DEF5" "Bounded fix iteration 4"
create_or_update_label "ai:iter-5" "C5DEF5" "Bounded fix iteration 5"

echo "Done."
