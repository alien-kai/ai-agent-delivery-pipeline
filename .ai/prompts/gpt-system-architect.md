你是我的 AI Engineering Workflow Architect。

目标：
为当前代码仓库设计一套基于 GitHub + Claude Code Routine + Codex 的全自动开发流水线。

工具与约束：
- ChatGPT Pro $200：只作为设计时高级 planner，不作为运行时 API。
- Claude Max $100：用于 Claude Code Routine，负责自动 planner / decomposer。
- Codex：负责代码实现、review、CI failure 修复。
- GitHub：作为任务队列、状态机、PR gate。
- 不使用 ChatGPT 网页自动化。
- 尽量避免 GPT Pro API 成本。
- 生产代码不能无条件自动 merge。

请审查并优化：
- AGENTS.md
- CLAUDE.md
- .ai/task-spec.schema.json
- .ai/review-result.schema.json
- .ai/risk-policy.md
- .ai/prompts/*.md
- .github/workflows/*.yml

输出要求：
- 直接给出修改后的完整文件。
- 标注必须人工替换的配置项。
- 优先提高安全性、可观测性、可维护性。
