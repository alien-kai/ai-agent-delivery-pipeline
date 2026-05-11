---
description: Convert an idea or GitHub issue into an AI task spec
argument-hint: [issue-id-or-idea]
---

请将以下输入转成 `.ai/tasks/{id}.yaml` 任务规格书：

`$ARGUMENTS`

要求：
- 先读取 `AGENTS.md`、`CLAUDE.md`、`.ai/risk-policy.md`、`.ai/task-spec.schema.json`。
- 如果输入包含 GitHub issue 编号，请读取对应 issue 内容；如果无法读取，就根据 `$ARGUMENTS` 创建本地 task spec 草案。
- 不要修改生产代码。
- 只允许创建或更新 `.ai/tasks/*.yaml`。
- risk_level 必须是 `green`、`yellow` 或 `red`。
- merge_policy 必须匹配 risk level：
  - green → `auto_merge_if_green`
  - yellow → `require_human`
  - red → `draft_only`
- 每个 implementation unit 必须足够小，适合交给 Codex 或 Claude 单独执行。
- 输出最后要给出下一步建议：`/ai-implement .ai/tasks/{id}.yaml` 或人工审批。
