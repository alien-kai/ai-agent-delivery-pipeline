---
description: Implement a task spec safely in Claude Code
argument-hint: [.ai/tasks/<id>.yaml]
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git checkout:*), Bash(git add:*), Bash(git commit:*), Bash(pnpm:*), Bash(npm:*), Bash(yarn:*), Bash(python:*), Bash(pytest:*), Bash(cargo:*), Bash(go test:*)
---

请执行这个 task spec：`$ARGUMENTS`

硬性规则：
- 先读取 `AGENTS.md`、`CLAUDE.md`、`.ai/risk-policy.md` 和指定 task spec。
- 如果 `risk_level: red` 或 `merge_policy: draft_only`，不要写生产代码，只输出实现计划和人工审批点。
- 只实现 task spec 中的 scope_in。
- 不做 scope_out 中的内容。
- 不新增依赖，除非 task spec 明确允许。
- 不改数据库 schema，除非 task spec 明确允许。
- 不读取、不打印 secrets。
- 不直接 push main。
- 修改后运行 task spec 的 verification_commands。

输出格式：

```md
## Implementation Summary

## Files Changed

## Tests Run

## Verification Result

## Remaining Risks

## Next Step
建议运行：/ai-codex-review
```
