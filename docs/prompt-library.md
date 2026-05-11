# Prompt Library：Claude Code + Codex Plugin

## 1. Claude Code 初始化 Prompt

```md
请先阅读 AGENTS.md、CLAUDE.md、.ai/risk-policy.md 和 docs/experiment-plan.md。

你现在是这个仓库的 AI delivery operator。
你的职责：
1. 将 idea 转成结构化 task spec。
2. 执行时严格遵守 task spec。
3. 每次实现后调用 Codex plugin 做独立 review。
4. 任何 auth/payment/database/privacy/secrets/production deployment 都必须停止并要求人工审批。

先不要写代码。请输出：
- 你理解的工作流
- 当前 repo 的关键控制文件
- 如何调用 /ai-plan、/ai-implement、/ai-codex-review
- 你会在哪些情况下拒绝自动实现
```

## 2. Idea → Task Spec Prompt

```md
请把下面的 idea 转成 .ai/tasks/{issue_id}.yaml 规格书。

要求：
- 遵守 .ai/task-spec.schema.json。
- 读取 .ai/risk-policy.md。
- 风险等级只能是 green/yellow/red。
- red 任务只能 plan，不允许自动实现。
- 每个 implementation unit 必须足够小，适合单独交给 Codex 执行。
- 输出必须包含 acceptance_criteria 和 verification_commands。

Idea：
$ARGUMENTS
```

## 3. Claude Code Implementation Prompt

```md
请执行 task spec：$ARGUMENTS

步骤：
1. 读取 AGENTS.md、CLAUDE.md、.ai/risk-policy.md。
2. 读取指定 task spec。
3. 如果 risk_level 是 red 或 merge_policy 是 draft_only，不要实现代码，只输出实现计划。
4. 如果可以实现，只做 task spec 内的范围。
5. 不新增依赖，除非 task spec 明确允许。
6. 修改后运行 verification_commands。
7. 总结 changed files、tests run、risks。
8. 最后提示我运行 /ai-codex-review。
```

## 4. Codex Review Prompt

```md
请使用 Codex plugin 对当前 diff 做 adversarial review。

重点检查：
- 是否符合 .ai/tasks/*.yaml
- 是否有缺失测试
- 是否有 scope creep
- 是否有 auth/payment/privacy/database/security 风险
- 是否有回归风险
- 是否有更小更安全的实现方式

建议命令：
/codex:adversarial-review --base main --background look for missing tests, scope creep, regressions, and security issues
```

## 5. Codex Rescue Prompt

```md
请使用 Codex plugin 修复上一次 review 中最高优先级的问题。

限制：
- 只修最高优先级问题。
- 不做无关优化。
- 不新增依赖。
- 不改数据库 schema。
- 修复后重新运行相关测试。

建议命令：
/codex:rescue --background fix the highest-priority issue with the smallest safe patch
```

## 6. PR Summary Prompt

```md
请根据当前 diff 生成 PR summary：

格式：
## Summary

## Task Spec

## Risk Level

## Changes

## Tests Run

## Codex Review Result

## Remaining Risks

## Merge Recommendation
```
