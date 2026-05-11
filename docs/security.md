# 安全策略

## 禁止事项

AI agents 不允许：

- push main
- deploy production
- 读取或打印 secrets
- 修改 `.env.production`
- 无授权新增依赖
- 无授权修改数据库 schema
- 无授权修改 auth/payment/privacy/permission 逻辑

## Secret 管理

以下内容必须作为 secrets 管理：

- `ROUTINE_FIRE_TOKEN`
- `ROUTINE_FIRE_URL`
- `OPENAI_API_KEY`，如果使用 API key
- `~/.codex/auth.json`，如果使用 ChatGPT-managed Codex auth

## Runner 安全

推荐：

- 私有 self-hosted runner
- 只服务私有 repo
- 最小权限 GitHub token
- 定期清理 workspace
- 避免在 runner 上保存生产环境 secrets

## Auto-merge 安全

仅允许 green lane 自动合并。

red lane 永远不自动合并。

yellow lane 必须人工批准。
