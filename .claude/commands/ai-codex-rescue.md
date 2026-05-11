---
description: Delegate the highest-priority fix to Codex plugin
argument-hint: [issue summary]
---

请调用 Codex plugin 修复最高优先级问题。

推荐命令：

```text
/codex:rescue --background fix the highest-priority issue with the smallest safe patch. Do not make unrelated changes. $ARGUMENTS
```

之后请运行：

```text
/codex:status
/codex:result
```

拿到结果后，请：
- 检查 diff 是否只修复目标问题
- 运行相关 verification_commands
- 输出是否可以进入 PR review
