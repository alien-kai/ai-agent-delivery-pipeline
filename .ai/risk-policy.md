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
