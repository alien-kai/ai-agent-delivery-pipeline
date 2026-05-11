# 设置 Codex Self-hosted Runner

## 目标

让 Codex CLI 在你的可信 self-hosted runner 上运行，用于执行、review、修 CI。

## 推荐方式

使用 ChatGPT subscription auth，而不是 `OPENAI_API_KEY`，以尽量使用订阅额度。

## 步骤

1. 准备一台可信机器，例如 Mac mini、私有 VPS、本地开发机或 homelab server。
2. 在 GitHub repo 中进入：

```text
Settings → Actions → Runners → New self-hosted runner
```

按页面提示安装并启动。

3. 安装 Codex CLI：

```bash
npm install -g @openai/codex
```

4. 设置 Codex auth 文件存储：

```bash
mkdir -p ~/.codex
cat > ~/.codex/config.toml <<'EOF'
cli_auth_credentials_store = "file"
EOF
```

5. 登录 Codex：

```bash
codex login
```

6. 确认不要误用 API key：

```bash
unset OPENAI_API_KEY
```

## 安全注意

- `~/.codex/auth.json` 要当成密码处理。
- 不要提交到 repo。
- 不要放在 artifact。
- 不要在 public runner 上使用。
- 不建议在 public/open-source repo 里使用 ChatGPT-managed auth。
