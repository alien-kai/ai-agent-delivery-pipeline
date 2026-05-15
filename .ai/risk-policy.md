# AI Risk Policy

## green

Allowed to auto-merge only if all conditions pass.

Examples:

- documentation update
- test addition
- small isolated bug fix
- lint fix
- type fix
- small UI copy change

Requirements:

- CI passes
- Codex review reports no P0/P1
- no dependency changes
- no database changes
- no auth/payment/privacy/security changes

Merge policy:

`auto_merge_if_green`

## yellow

Allowed to auto-implement, but requires human approval before merge.

Examples:

- new feature
- API behavior change
- multi-file refactor
- user-visible behavior change
- performance optimization

Merge policy:

`require_human`

## red

Allowed to plan only or open draft PR only.

Examples:

- authentication
- authorization
- payments
- database migration
- data deletion
- secrets
- privacy
- production deployment
- compliance
- permission model changes

Merge policy:

`draft_only`

## unknown

Reserved for runtime parser failures and reviewer outputs. Planners must
not produce `risk_level: unknown` in a task spec. If a planner is
uncertain it must choose `yellow` (auto-implement, human merge) or
`red` (plan-only) — never `unknown`.

When a Codex review result reports `risk_level: unknown` (e.g., a
malformed output or a parse failure), the pipeline must label the PR
`ai:human-required` and must not enter the AI fix loop.

Merge policy:

`require_human`

## AI fix loop bounds

The AI fix loop turns review findings into a Codex repair commit and
then re-runs review. To prevent runaway loops:

- The maximum number of automatic fix iterations per PR is read from
  the task spec's `max_iterations`. Default is 2. Allowed range is 0–5.
- `max_iterations: 0` disables the AI fix loop for that task; review
  findings always escalate to a human.
- `allow_auto_fix: false` disables the AI fix loop for that task,
  regardless of `max_iterations`.
- Each iteration is recorded on the PR as label `ai:iter-N`.
- When `N >= max_iterations`, the workflow labels the PR
  `ai:max-iterations-reached` and `ai:human-required`. No further
  automatic fix attempt is made.

### Severity routing

- **P0 finding** → always `ai:human-required`. Never auto-fix.
- **P1 finding** → auto-fix only when all of:
  - risk is `green` or `yellow`,
  - `allow_auto_fix` is true,
  - current iteration < `max_iterations`.
- **P2 finding** → may auto-fix under the same conditions, but a P2
  alone does not block green-lane auto-merge if no P0/P1 are present.

### Risk routing

- `red` task → never auto-fix. Plan-only or draft PR only.
- `unknown` (review result) → never auto-fix.

### Merge routing

- `green` task → auto-merge eligible only when review reports no P0/P1
  and CI is green.
- `yellow` task → auto-implement allowed; auto-fix loop allowed; merge
  requires human approval.
- `red` task → planning or draft PR only; no auto-implement, no
  auto-fix, no auto-merge.
