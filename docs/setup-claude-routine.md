# 设置 Claude Code Routine

## 目标

让 Claude Code Routine 负责把 GitHub issue 转换成 `.ai/tasks/{issue}.yaml`，并创建 `[AI PLAN]` PR。

## 步骤

1. 打开 Claude Code Routines。
2. 创建新 Routine：

```text
Name: AI Planner - GitHub Issue to Task Spec
```

3. 选择本 GitHub repo。
4. Prompt 使用：

```text
.ai/prompts/claude-planner-routine.md
```

5. Environment：
   - 默认即可。
   - 需要额外网络访问时，再配置 allowlist。

6. Trigger：
   - 添加 API trigger。
   - 保存 `ROUTINE_FIRE_URL`。
   - 生成并保存 `ROUTINE_FIRE_TOKEN`。

7. 在 GitHub repo secrets 中添加：

```text
ROUTINE_FIRE_URL
ROUTINE_FIRE_TOKEN
```

## 注意

- Routine 只负责 planning，不写生产代码。
- Routine 的 PR 只能包含 `.ai/tasks/*.yaml`。
- `ai-plan-automerge.yml` 会拒绝包含其他文件的 plan PR。
- Routine token 必须当作 secret 保存。
