# AGENTS.md

## Repository role

This repository uses AI agents for planning, implementation, review, and CI repair.

Codex is allowed to:

- read the repository
- modify files inside the repository
- run project test commands
- create implementation branches
- prepare pull requests

Codex is not allowed to:

- push directly to main
- read or print secrets
- modify `.env.production`
- deploy to production
- modify database schema unless the task spec explicitly permits it
- add production dependencies unless the task spec explicitly permits it
- make unrelated refactors
- bypass tests

## Required workflow

Before editing code:

1. Read `.ai/risk-policy.md`.
2. Read the relevant `.ai/tasks/*.yaml` task spec.
3. Confirm the task risk level.
4. Identify files likely to change.
5. Implement only the requested scope.

After editing code:

1. Run relevant tests.
2. Run typecheck.
3. Run lint.
4. Summarize changed files.
5. Summarize tests run.
6. Summarize remaining risks.

## Commands

Replace these with the real project commands.

- Install dependencies: `pnpm install`
- Typecheck: `pnpm typecheck`
- Lint: `pnpm lint`
- Unit tests: `pnpm test`
- Integration tests: `pnpm test:integration`
- E2E tests: `pnpm test:e2e`

## Review guidelines

Treat the following as P0/P1:

- auth regression
- payment regression
- permission bug
- privacy/data leak
- database migration without rollback plan
- missing tests for changed business logic
- production secret exposure
- unrelated broad refactor
- CI skipped or ignored
- behavior not matching `.ai/tasks/*.yaml`

## Definition of done

A task is complete only when:

- implementation matches the task spec
- relevant tests are added or updated
- required commands pass
- no unrelated files are changed
- risks are documented
- PR summary includes verification results
