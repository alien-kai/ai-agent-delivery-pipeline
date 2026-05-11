# 日常操作

## 创建 AI 任务

创建 GitHub issue，使用模板 `AI Task`，并确保有 label：

```text
ai:plan
```

## 检查规划结果

Claude Routine 会创建：

```text
[AI PLAN] Issue #...: ...
```

这个 PR 如果只改 `.ai/tasks/*.yaml`，会被自动合并。

## 检查实现 PR

Codex 会创建：

```text
[AI IMPL] issue-...
```

PR 会被自动打上：

```text
ai:review
risk:green | risk:yellow | risk:red
```

## 自动合并

只有满足以下条件时才允许 green auto-merge：

- PR 标题以 `[AI IMPL]` 开头。
- PR 有 `risk:green`。
- PR 有 `ai:auto-merge-eligible`。
- CI / branch protection 允许合并。

## CI 失败

给 PR 加 label：

```text
ai:ci-failed
```

会触发 Codex CI fixer。

## 人工介入条件

- `risk:yellow`
- `risk:red`
- `ai:human-required`
- Codex review 有 P0/P1
- CI fixer 两次失败
- PR 涉及 auth/payment/privacy/database/secrets/deployment
