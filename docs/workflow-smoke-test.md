# Workflow Smoke Test

This document verifies that the AI delivery workflow can complete a low-risk documentation-only task.

## Expected flow

1. A task spec is created under `.ai/tasks/`.
2. Claude Code or Codex implements only the requested documentation change.
3. Codex reviews the branch diff against `main`.
4. The review should confirm that the change stays within task scope.

## Acceptance criteria

- No source files are modified.
- No scripts are modified.
- No dependencies are added.
- No database, auth, payment, privacy, or deployment files are changed.
