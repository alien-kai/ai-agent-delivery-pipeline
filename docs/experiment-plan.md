# 实验方案：Claude Code + Codex Plugin AI Delivery Pipeline

## 目标

验证一套低人工介入的 AI 研发流水线：

```text
Idea / GitHub Issue
  → Claude Code planner
  → Task Spec
  → Claude Code implementation session
  → Codex plugin review / rescue
  → PR / CI / merge gate
```

本实验重点不是一开始就追求完全无人值守，而是先验证：

1. Claude Code 能否稳定把 idea 拆成 Codex 可执行的 task spec。
2. Claude Code + Codex plugin 能否在本地完成“实现 + 交叉 review”。
3. Codex review gate 是否能拦住明显 bug、缺测试和越界修改。
4. GitHub issue / PR / labels 是否足够作为自动化状态机。

## 实验分组

### Phase 0：环境验证

目标：确认 Claude Code、Codex CLI、Codex plugin 都可用。

操作：

```text
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
/codex:review --background
/codex:status
/codex:result
```

通过标准：

- `/codex:setup` 显示 Codex ready。
- `/codex:review --background` 能启动任务。
- `/codex:result` 能返回结果。

### Phase 1：手动半自动基线

目标：建立可控的人工-代理流程。

流程：

```text
创建 issue
→ 用 /ai-plan 生成 task spec
→ 用 /ai-implement 执行
→ 用 /ai-codex-review 调 Codex review
→ 人工判断是否提交 PR
```

通过标准：

- Claude Code 只按 task spec 改动文件。
- Codex review 能发现至少一类问题：缺测试、范围越界、安全风险或设计风险。
- 你能在 15 分钟内完成一个 green 任务闭环。

### Phase 2：GitHub 自动 planner

目标：把 `ai:plan` issue 自动变成 `.ai/tasks/{issue}.yaml`。

流程：

```text
Issue + ai:plan label
→ GitHub Action
→ Claude Routine API trigger
→ Claude 创建 [AI PLAN] PR
→ Plan PR 自动合并
```

通过标准：

- Plan PR 只包含 `.ai/tasks/*.yaml`。
- task spec 能独立表达目标、范围、风险、验收标准和验证命令。

### Phase 3：本地 Codex plugin 强化执行

目标：在 Claude Code 本地会话里，把 Codex 作为 reviewer / rescue agent。

推荐顺序：

```text
/ai-implement .ai/tasks/123.yaml
/codex:adversarial-review --base main --background look for missing tests, scope creep, and regression risk
/codex:status
/codex:result
```

如果 Codex 发现问题：

```text
/codex:rescue --background fix the highest-priority issue with the smallest safe patch
/codex:status
/codex:result
```

通过标准：

- Claude 和 Codex 不同时大范围改同一块逻辑。
- Codex rescue 只做最小修复。
- 最终 diff 能通过项目测试。

### Phase 4：Codex 自动执行与 review

目标：由 self-hosted runner 调用 Codex CLI，把 task spec 转为 PR。

流程：

```text
.ai/tasks/*.yaml 合入 main
→ ai-execute-codex.yml
→ Codex 创建 [AI IMPL] PR
→ ai-review-codex.yml
→ Codex review comment
→ green 自动 merge；yellow/red 人工 approve
```

通过标准：

- green 任务自动 PR 成功率 ≥ 70%。
- Codex review 无 P0/P1 后才打 `ai:auto-merge-eligible`。
- yellow/red 不自动 merge。

## 实验任务样本

### Green 样本

```text
任务：为 README 增加一个 FAQ section。
限制：只允许修改 README.md。
验收：README 包含 FAQ；无代码变更。
```

### Yellow 样本

```text
任务：增加一个前端 settings panel。
限制：不改数据库，不新增生产依赖。
验收：组件有测试，现有页面不回归。
```

### Red 样本

```text
任务：修改登录权限逻辑。
限制：只能生成 plan 或 draft PR，不允许自动 merge。
验收：必须人工 review。
```

## 观测指标

| 指标 | 目标 |
|---|---|
| task spec 可执行率 | ≥ 80% |
| green 任务自动完成率 | ≥ 70% |
| 越界改动率 | ≤ 10% |
| Codex review 有效问题发现率 | ≥ 30% |
| 需要人工修 prompt 的比例 | 每周下降 |
| API 额外成本 | 尽量为 0 |

## 停止条件

出现以下情况时，不要继续自动化，先调整 prompt / policy：

- Claude planner 频繁把 yellow/red 判成 green。
- Codex 经常改任务外文件。
- review gate 形成长循环并明显消耗额度。
- CI fixer 反复扩大修改范围。
- 自动 merge 合入过明显错误。

## 复盘模板

每周复盘一次：

```md
# Weekly AI Pipeline Review

## Completed tasks
- 

## Failed tasks
- 

## Prompt issues
- 

## Risk classification mistakes
- 

## Codex review misses
- 

## Changes to make next week
- 
```
