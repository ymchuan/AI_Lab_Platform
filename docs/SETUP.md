# 部署指南

从零部署 LabAgent Platform 的完整步骤。

## 设备清单

| 设备 | 用途 | 状态 |
|------|------|------|
| 5090 (RTX 5090 32GB) | 主力推理 | ✅ 已配置 LM Studio；Qwen3-Coder-30B 已定为 `qwen-agent` 默认模型 |
| 新设备 (RTX 5080 16GB + RTX 4060 Ti 16GB) | Embedding / Vision / 第二推理 / Rerank | ✅ `embed-local` / `vision-local` 已接入；Rerank 待配置 |
| 8060S (AMD 395 / 31.6GB) | 暂不规划 | ⛔ 当前无法使用，冻结接入 |
| 云服务器 (Ubuntu 24.04, 2核 2GB) | 轻量 API 网关 / 隧道中转 | ✅ 已配置，短期无法升级 |

## 步骤 1：本地模型部署（每台 GPU 主机）

1. 安装 LM Studio
2. 下载模型
3. 启动 Local Server：
   - Server Running = ON
   - Serve on Local Network = OFF（推荐正式路线；只通过本机 SSH 反向隧道转发）
   - Require Authentication = OFF
4. 验证：`curl http://127.0.0.1:1234/v1/models`

新设备 embedding v1 当前使用：

```text
LM Studio model id: text-embedding-nomic-embed-text-v1.5-embedding
公网 LiteLLM alias: embed-local
```

新设备 vision v1 当前使用：

```text
LM Studio model id: qwen/qwen3-vl-30b
公网 LiteLLM alias: vision-local
```

## 步骤 2：SSH 密钥认证（每台 GPU 主机）

```bash
# 生成密钥
ssh-keygen -t ed25519

# 上传公钥（Windows PowerShell）
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh ubuntu@82.156.69.153 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# 验证
ssh ubuntu@82.156.69.153 "echo ok"
```

## 步骤 3：SSH 反向隧道（每台 GPU 主机）

当前 SSH 反向隧道不是常驻状态。公网验证前，必须先在 5090 手动开启 `:12340` 隧道。

```bash
# 5090（端口 12340）
ssh -N -R 12340:127.0.0.1:1234 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153

# 新设备（端口 12341）
ssh -N -R 12341:127.0.0.1:1234 -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

8060S 当前无法使用，不再配置 `:12342` 隧道。

## 步骤 4：云服务器 LiteLLM

```bash
# 安装
sudo apt update && sudo apt install -y python3-pip python3-venv
mkdir -p ~/litellm-gateway && cd ~/litellm-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install 'litellm[proxy]'

# 配置（按实际接入的节点修改 api_base 端口）
cat > config.yaml <<'EOF'
model_list:
  - model_name: qwen-local
    litellm_params:
      model: openai/qwen/qwen3-coder-30b
      api_base: http://127.0.0.1:12340/v1
      api_key: lm-studio
  - model_name: qwen-agent
    litellm_params:
      model: openai/qwen/qwen3-coder-30b
      api_base: http://127.0.0.1:12340/v1
      api_key: lm-studio
  - model_name: embed-local
    litellm_params:
      model: openai/text-embedding-nomic-embed-text-v1.5-embedding
      api_base: http://127.0.0.1:12341/v1
      api_key: lm-studio
  - model_name: vision-local
    litellm_params:
      model: openai/qwen/qwen3-vl-30b
      api_base: http://127.0.0.1:12341/v1
      api_key: lm-studio
general_settings:
  master_key: <LABAGENT_API_KEY>
EOF

# systemd 服务
sudo tee /etc/systemd/system/litellm-gateway.service > /dev/null <<'EOF'
[Unit]
Description=LiteLLM API Gateway
After=network.target
[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/litellm-gateway
ExecStart=/home/ubuntu/litellm-gateway/.venv/bin/litellm --config /home/ubuntu/litellm-gateway/config.yaml --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable litellm-gateway
sudo systemctl start litellm-gateway
```

## 步骤 5：SSH 保活配置

```bash
sudo sed -i 's/#ClientAliveInterval 0/ClientAliveInterval 30/' /etc/ssh/sshd_config
sudo sed -i 's/#ClientAliveCountMax 3/ClientAliveCountMax 10/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## 步骤 6：安全组配置

```text
TCP 8000 — LiteLLM API
TCP 3000 — OpenWebUI（需要时开放；不建议云服务器常驻）
```

## 步骤 7：OpenWebUI（需要时启动或迁移到本地节点）

云服务器只有 2GB 内存且短期无法升级。OpenWebUI 可用于临时演示，但不建议长期和 LiteLLM 同时常驻。后续更推荐将 OpenWebUI 部署到 5090 或新设备，通过云服务器反向代理/隧道访问。

```bash
cd ~/open-webui && source .venv/bin/activate
OPENAI_API_BASE_URL=http://127.0.0.1:8000/v1 \
OPENAI_API_KEY=<LABAGENT_API_KEY> \
RAG_EMBEDDING_ENGINE=openai \
RAG_EMBEDDING_MODEL=embed-local \
open-webui serve --port 3000 --host 0.0.0.0
```

## 步骤 8：客户端配置

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <LABAGENT_API_KEY>
Model: qwen-local
```

Embedding 客户端使用：

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <LABAGENT_API_KEY>
Model: embed-local
Endpoint: /v1/embeddings
```

Vision 客户端使用：

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <LABAGENT_API_KEY>
Model: vision-local
Endpoint: /v1/chat/completions
Message format: OpenAI image_url content block
```

## 步骤 9：另一台机器验证全链路

公网验证前，先在 5090 上确认 LM Studio Local Server 正在运行，然后开启反向隧道：

```powershell
ssh -N -R 12340:127.0.0.1:1234 -i C:\Users\N\.ssh\id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

在另一台机器上验证模型列表：

```powershell
curl.exe http://82.156.69.153:8000/v1/models -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

继续验证 chat completion。只有这一步成功，才算公网全链路打通：

```powershell
curl.exe http://82.156.69.153:8000/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"qwen-local\",\"messages\":[{\"role\":\"user\",\"content\":\"用一句话回答：链路是否打通？\"}],\"max_tokens\":80,\"temperature\":0.2}"
```

如果 `/v1/models` 成功但 `/v1/chat/completions` 失败，优先确认 5090 的 SSH 隧道窗口是否仍在运行。

验证新设备 embedding 路由：

```powershell
curl.exe http://82.156.69.153:8000/v1/embeddings `
  -H "Authorization: Bearer <LABAGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  --data-raw '{ "model": "embed-local", "input": "hello labagent" }'
```

验证新设备 vision 路由：

```powershell
curl.exe http://82.156.69.153:8000/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  --data-raw '{ "model": "vision-local", "messages": [{"role":"user","content":[{"type":"text","text":"请描述图片内容并读出可见文字。"},{"type":"image_url","image_url":{"url":"data:image/png;base64,<BASE64_IMAGE>"}}]}], "max_tokens": 500 }'
```

## 步骤 10：启动并验证 RAG Service v1 公网入口

RAG Service v1 运行在 5090，不在新设备上运行。它读取 5090 本地 `data/rag/index.json`，embedding 可通过云端 LiteLLM 路由到新设备 `embed-local`，chat 可直连 5090 本机 LM Studio。

在 5090 PowerShell 启动服务：

```powershell
cd E:\qwen_setup
Get-Content .env.local | ForEach-Object {
  $p = $_.Split("=", 2)
  if ($p.Count -eq 2) { [Environment]::SetEnvironmentVariable($p[0], $p[1]) }
}
python -m services.rag.server --host 127.0.0.1 --port 8010
```

另开一个 5090 PowerShell 窗口，开启公网反向隧道：

```powershell
ssh -N -R 0.0.0.0:18010:127.0.0.1:8010 -i C:\Users\N\.ssh\id_ed25519 `
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
  ubuntu@82.156.69.153
```

公网验证：

```powershell
curl.exe http://82.156.69.153:18010/health -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

2026-06-26 状态：本地 HTTP 四端点已通过，公网 `/health` 已由 David 外部机器验证返回 `ok=true`。当前服务和隧道仍需手动维持，关闭对应 PowerShell 窗口后公网 RAG 入口会停止。
