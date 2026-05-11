# AI Agent Delivery Pipeline

这是一个用于把 **idea → 自动规划 → 自动实现 → 自动 review → CI 验证 → 低风险自动合并** 串起来的 GitHub 自动化仓库模板。

核心分工：

- **GPT Pro**：设计时大脑。负责优化 prompt、schema、risk policy、workflow，不作为 runtime API。
- **GitHub**：任务队列、状态机、PR gate、审计日志。
- **Claude Code Routine**：自动 planner / decomposer。把 GitHub issue 转成 `.ai/tasks/{issue}.yaml`。
- **Codex**：自动 executor / reviewer / CI fixer。根据 task spec 写代码、创建 PR、review、修 CI。
- **CI**：最终裁判。

---

## 工作流

```text
GitHub Issue + label ai:plan
        ↓
GitHub Action: ai-plan.yml
        ↓
Claude Code Routine API trigger
        ↓
Claude creates [AI PLAN] PR with .ai/tasks/{issue}.yaml
        ↓
Plan PR auto-merge if it only changes .ai/tasks/*.yaml
        ↓
GitHub Action: ai-execute-codex.yml
        ↓
Codex implements on feature branch
        ↓
Codex opens [AI IMPL] PR
        ↓
CI + ai-review-codex.yml
        ↓
Codex adversarial review
        ↓
risk:green auto-merge; risk:yellow/risk:red require human approval
```

---

## 快速开始

### 1. 推送到 GitHub

本模板内置 `gh` CLI bootstrap 脚本：

```bash
gh auth login
chmod +x scripts/*.sh
./scripts/bootstrap-github.sh alien-kai ai-agent-delivery-pipeline private
```

参数：

```text
第 1 个参数：GitHub owner，例如 alien-kai
第 2 个参数：repo name，例如 ai-agent-delivery-pipeline
第 3 个参数：private 或 public
```

### 2. 创建 labels

```bash
./scripts/create-labels.sh
```

### 3. 创建 Claude Code Routine

阅读：

```text
docs/setup-claude-routine.md
```

创建 Routine 后，把 API trigger 的 URL 和 token 加到 GitHub Secrets：

```text
ROUTINE_FIRE_URL
ROUTINE_FIRE_TOKEN
```

### 4. 配置 Codex self-hosted runner

阅读：

```text
docs/setup-codex-self-hosted-runner.md
```

核心命令：

```bash
npm i -g @openai/codex
codex login
```

如果你想使用 ChatGPT subscription auth，而不是 API 计费，请不要在 runner 环境里设置 `OPENAI_API_KEY`。

### 5. 开始使用

创建 GitHub issue，使用 `AI Task` 模板，或手动添加 label：

```text
ai:plan
```

---

## 风险分层

### green：可自动合并

- docs
- tests
- 小 bug fix
- lint/type 修复
- 小范围 UI copy

条件：

- CI 通过
- Codex review 无 P0/P1
- 没有 auth/payment/permission/privacy/database/secrets/deployment 风险

### yellow：自动实现，人工批准

- 新 feature
- API 行为变化
- 多文件重构
- 用户可见行为变化
- 性能优化

### red：只允许 plan 或 draft PR

- auth
- payment
- permission
- database migration
- privacy
- secrets
- production deployment
- data deletion
- compliance

---

## 需要你替换的内容

- `AGENTS.md` 里的真实项目命令
- `CLAUDE.md` 里的项目上下文
- `.ai/prompts/*` 中的技术栈细节
- GitHub Secrets: `ROUTINE_FIRE_URL`, `ROUTINE_FIRE_TOKEN`
- self-hosted runner 环境
- branch protection / required checks


---

## Claude Code + Codex Plugin 本地实验

本仓库同时支持两种模式：

1. **本地半自动模式**：在 Claude Code 中使用项目 slash commands 和 Codex plugin。
2. **GitHub 自动化模式**：用 GitHub issue/labels 触发 Claude Routine 和 Codex runner。

本地模式建议先跑通：

```text
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

然后使用项目命令：

```text
/ai-plan <你的 idea 或 issue 编号>
/ai-implement .ai/tasks/<id>.yaml
/ai-codex-review
/ai-codex-rescue <最高优先级问题>
```

实验方案见：

```text
docs/experiment-plan.md
docs/prompt-library.md
```
