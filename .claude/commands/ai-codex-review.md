---
description: Run Codex plugin adversarial review for current branch
argument-hint: [optional focus]
---

请调用 Codex plugin 对当前分支做独立审查。

推荐先运行：

```text
/codex:adversarial-review --base main --background look for missing tests, scope creep, regressions, security issues, and mismatch with task spec. $ARGUMENTS
```

然后运行：

```text
/codex:status
```

如果任务完成，再运行：

```text
/codex:result
```

请在拿到 Codex 结果后，总结：
- P0/P1/P2 findings
- 是否允许继续 PR
- 是否需要 `/codex:rescue`
- 是否需要人工 review
