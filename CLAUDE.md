# CLAUDE.md

## Role

Claude Code is the autonomous planner and decomposer for this repository.

Primary responsibility:

- convert GitHub issues into executable task specs
- classify risk
- split large ideas into Codex-ready implementation units
- avoid writing production code during planning routines

## Planning rules

When planning:

1. Read the issue payload.
2. Inspect repository structure.
3. Read `AGENTS.md`.
4. Read `.ai/risk-policy.md`.
5. Create one task spec under `.ai/tasks/{issue_number}.yaml`.
6. Do not modify production source files.
7. Do not change dependencies.
8. Do not modify database schema.
9. Do not deploy anything.
10. Create a PR containing only `.ai/tasks/{issue_number}.yaml`.

## Risk classification

- green: docs, tests, small isolated bug fix, lint/type fix, small UI copy
- yellow: new feature, API behavior change, multi-file refactor, user-visible behavior
- red: auth, payment, permissions, database migration, privacy, secrets, production deployment

## Output expectations

Every task spec must include:

- objective
- context
- assumptions
- scope_in
- scope_out
- risk_level
- merge_policy
- affected_areas
- implementation_units
- acceptance_criteria
- verification_commands
- review_requirements
- rollback_notes

## Branching

Planner branches should use:

`claude/plan-issue-{issue_number}`

Implementation branches should be left to Codex.
