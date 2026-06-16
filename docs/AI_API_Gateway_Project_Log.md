# 私有 AI API 网关项目复盘

> 当前目标：把 5090 本机部署的大模型通过云服务器暴露成 OpenAI-compatible API，让其他机器、插件和程序可以像调用 OpenAI 一样调用本地模型。

## 当前状态校准（2026-06-10）

本文件保留早期部署和排障过程中的历史记录，其中部分模型列表、测试 key 和临时配置来自当时环境，不代表当前状态。

当前事实以 `README.md`、`HANDOFF.md`、`docs/ARCHITECTURE.md`、`docs/API.md` 为准：

- 云服务器：Ubuntu 24.04，2 核 2GB，短期无法升级。
- 当前已接入模型：只有 5090 上的 `qwen/qwen3.6-27b`，经 `qwen-local` 暴露。
- 新设备和 8060S：尚未配置模型、隧道或 LiteLLM 路由。
- 真实 API Key 已从文档中脱敏，统一使用 `<LABAGENT_API_KEY>` 占位符。

## 1. 项目背景

### 1.1 初始目标

本项目不是单纯在本地运行一个大模型，而是逐步建设一个可复用的私有 AI 基础设施平台。

当前最小目标是：

```text
其他机器 / VS Code 插件 / Agent 程序
        |
        v
云服务器公网 Base URL
        |
        v
5090 本机 LM Studio / 本地大模型
```

也就是让外部使用者可以配置类似 OpenAI 的参数：

```text
Base URL: http://云服务器地址:端口/v1
API Key: 自定义 key
Model: qwen-local 或其他模型名
```

### 1.2 长期方向

后续可以迭代为：

- 私有 OpenAI-compatible API 网关
- LiteLLM 多模型统一入口
- vLLM 高性能推理服务
- 多节点模型调度
- 8060S 辅助节点，承载 Whisper、OCR、Embedding、VL 等任务
- OpenWebUI / Cline / Roo Code / Continue / Cursor 等前端接入
- 面向简历展示的 AI Infra / Agent Platform 项目

## 2. 当前硬件与网络环境

### 2.1 节点 A：5090 本地推理节点

当前正在使用的主设备就是 5090 机器。

已知信息：

- GPU：RTX 5090 32GB
- 系统：Windows 11
- 内网 IP：172.16.14.240
- 已部署：LM Studio
- 已开启：OpenAI Compatible API
- LM Studio 本地接口：

```text
http://127.0.0.1:1234/v1
```

- LM Studio 局域网接口：

```text
http://172.16.14.240:1234/v1
```

当前模型列表曾成功返回：

```text
qwen/qwen3.6-27b
google/gemma-4-31b
text-embedding-nomic-embed-text-v1.5
```

### 2.2 节点 B：8060S 辅助节点

已知信息：

- AMD Ryzen AI MAX+ 395 / Radeon 8060S
- 实际为 32GB 统一内存版本
- 内网 IP：172.16.14.142
- 当前判断：不适合作为主力大模型推理节点
- 更适合后续承担：
  - Whisper
  - MinerU
  - OCR
  - Embedding
  - Qwen2.5-VL / 多模态任务

### 2.3 节点 C：腾讯云 Ubuntu 云服务器

已知信息：

- 系统：Ubuntu 24.04
- 公网 IP：82.156.69.153
- 用户：ubuntu
- SSH 端口：22
- SSH 服务已确认可用

云服务器当前角色：

```text
公网入口 / API Gateway / LiteLLM / Nginx / 反向隧道中转节点
```

## 3. 已完成步骤

### 3.1 确认 LM Studio 本地 OpenAI-compatible API 可用

目标：确认 5090 本机上的 LM Studio 已经能提供 OpenAI-compatible API。

测试方式：

```bash
curl http://127.0.0.1:1234/v1/models
```

期望现象：返回模型列表。

状态：已通过云服务器反向访问间接确认 LM Studio API 可用。

### 3.2 确认校园网限制

发现的问题：

- 5090 位于校园网 / 内网环境
- 内网地址为 `172.16.x.x`
- 外部无法直接访问 5090 的 `1234` 端口
- 没有公网 IP
- 没有端口映射权限
- FRP / Tailscale / ZeroTier 等方案虽然技术上可行，但当前阶段不优先使用，避免被认为是 VPN / 内网穿透行为

结论：

```text
不能直接把 5090:1234 暴露到公网，需要通过云服务器中转。
```

### 3.3 选择 SSH Reverse Tunnel 方案

当前采用 SSH 反向隧道：

```text
云服务器 127.0.0.1:12340
        |
        v
SSH Reverse Tunnel
        |
        v
5090 本机 127.0.0.1:1234
        |
        v
LM Studio OpenAI-compatible API
```

在 5090 Windows PowerShell 中执行：

```bash
ssh -N -R 12340:127.0.0.1:1234 ubuntu@82.156.69.153
```

含义：

```text
把云服务器本机的 12340 端口，反向转发到 5090 本机的 1234 端口。
```

### 3.4 在云服务器验证反向隧道成功

在云服务器执行：

```bash
curl http://127.0.0.1:12340/v1/models
```

实际返回：

```json
{
  "data": [
    {
      "id": "qwen/qwen3.6-27b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "google/gemma-4-31b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "text-embedding-nomic-embed-text-v1.5",
      "object": "model",
      "owned_by": "organization_owner"
    }
  ],
  "object": "list"
}
```

结论：

```text
云服务器已经可以通过 127.0.0.1:12340 访问 5090 本机 LM Studio API。
```

这是项目第一个关键里程碑。

## 4. 当前待执行步骤：部署 LiteLLM 网关

### 4.1 为什么需要 LiteLLM

现在云服务器只能自己访问：

```text
http://127.0.0.1:12340/v1
```

但其他机器还不能直接访问。

下一步需要在云服务器上部署 LiteLLM，把它包装成公网可访问的 API：

```text
http://82.156.69.153:8000/v1
```

LiteLLM 的作用：

- 提供 OpenAI-compatible API 网关
- 给外部调用方设置 API Key
- 给模型起更好用的别名，例如 `qwen-local`
- 后续可统一接入多个后端模型
- 后续可以接 Nginx、HTTPS、域名、访问控制

### 4.2 云服务器安装 LiteLLM

在云服务器执行：

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
mkdir -p ~/litellm-gateway
cd ~/litellm-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install 'litellm[proxy]'
```

### 4.3 创建 LiteLLM 配置文件

在云服务器执行：

```bash
cat > ~/litellm-gateway/config.yaml <<'EOF'
model_list:
  - model_name: qwen-local
    litellm_params:
      model: openai/qwen/qwen3.6-27b
      api_base: http://127.0.0.1:12340/v1
      api_key: lm-studio

  - model_name: gemma-local
    litellm_params:
      model: openai/google/gemma-4-31b
      api_base: http://127.0.0.1:12340/v1
      api_key: lm-studio

  - model_name: nomic-embed-local
    litellm_params:
      model: openai/text-embedding-nomic-embed-text-v1.5
      api_base: http://127.0.0.1:12340/v1
      api_key: lm-studio

general_settings:
  master_key: <OLD_TEST_API_KEY>
EOF
```

说明：

- `qwen-local` 是对外暴露的模型名
- `openai/qwen/qwen3.6-27b` 表示 LiteLLM 使用 OpenAI-compatible 后端
- `api_base` 指向云服务器本机的 SSH 隧道入口
- `master_key` 是调用 LiteLLM 时使用的 API Key

注意：

```text
<OLD_TEST_API_KEY> 只是临时测试 key，后续需要换成更安全的 key。
```

### 4.4 启动 LiteLLM

在云服务器第一个终端执行：

```bash
cd ~/litellm-gateway
source .venv/bin/activate
litellm --config config.yaml --host 0.0.0.0 --port 8000
```

这个终端需要保持打开。

### 4.5 在云服务器本机测试 LiteLLM

在云服务器第二个终端执行：

```bash
curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer <OLD_TEST_API_KEY>"
```

测试聊天：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer <OLD_TEST_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [
      {"role": "user", "content": "你好，请用一句话介绍你自己"}
    ]
  }'
```

如果成功，说明：

```text
LiteLLM -> SSH Reverse Tunnel -> LM Studio -> Qwen
```

链路已经跑通。

## 5. LiteLLM 网关验证结果

### 5.1 `/v1/models` 验证成功

在云服务器第二个终端执行：

```bash
curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer <OLD_TEST_API_KEY>"
```

实际返回包含：

```text
qwen-local
gemma-local
nomic-embed-local
```

结论：

```text
LiteLLM 已成功读取配置文件，并对外暴露了三个模型别名。
```

### 5.2 `/v1/chat/completions` 验证成功

在云服务器第二个终端执行：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer <OLD_TEST_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [
      {"role": "user", "content": "你好，请用一句话介绍你自己"}
    ]
  }'
```

实际返回：

```text
你好，我是由阿里巴巴通义实验室研发的通义千问，致力于成为你真诚、有益的思维伙伴。
```

同时响应中显示：

```text
model: qwen-local
system_fingerprint: qwen/qwen3.6-27b
```

结论：

```text
LiteLLM -> SSH Reverse Tunnel -> 5090 LM Studio -> qwen/qwen3.6-27b
```

完整链路已经跑通。

这是项目第二个关键里程碑：云服务器本机已经可以通过 LiteLLM OpenAI-compatible API 调用 5090 本地大模型。

### 5.3 公网 `/v1/models` 验证成功

在腾讯云控制台放行 TCP 8000 入站规则后，从 5090 本机 PowerShell 执行：

```powershell
Invoke-RestMethod -Uri "http://82.156.69.153:8000/v1/models" -Headers @{ Authorization = "Bearer <OLD_TEST_API_KEY>" }
```

实际返回包含：

```text
qwen-local
gemma-local
nomic-embed-local
```

结论：

```text
外部机器 -> 云服务器公网 82.156.69.153:8000 -> LiteLLM -> SSH Reverse Tunnel -> 5090 LM Studio
```

公网 OpenAI-compatible API 已经打通。

这是项目第三个关键里程碑：其他机器已经可以通过云服务器公网 Base URL 调用 5090 本地大模型。

当前可用于 OpenAI-compatible 客户端的配置为：

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <OLD_TEST_API_KEY>
Model: qwen-local
```

安全注意：当前测试 key 较弱，且若安全组来源为 `0.0.0.0/0`，只适合临时验证。后续应改为强 API Key，并限制安全组来源 IP，或引入 Nginx + HTTPS。

### 5.4 当前发现的小问题：Qwen reasoning 内容被返回

现象：

响应中除了最终回答，还返回了大量 `reasoning_content` / `Thinking Process` 内容。

影响：

- 说明模型调用本身是成功的；
- 但后续接入客户端时，可能会看到不必要的思考过程；
- 会增加 token 消耗和响应体体积。

后续处理方向：

- 在 LM Studio 中检查 Qwen 模型的 reasoning / thinking 输出设置；
- 或在 LiteLLM / 客户端侧配置过滤；
- 若换用 coder / instruct 模型，也需要单独验证输出格式。

## 6. 后续公网访问配置

当云服务器本机 LiteLLM 测试成功后，再处理公网访问。

### 5.1 外部访问地址

目标外部配置：

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <OLD_TEST_API_KEY>
Model: qwen-local
```

### 5.2 如果外部访问不通，优先检查

已执行排查：

```bash
ss -tlnp | grep :8000
```

实际返回：

```text
LISTEN 0 2048 0.0.0.0:8000 0.0.0.0:* users:(("litellm",pid=63553,fd=13))
```

结论：LiteLLM 已正确监听 `0.0.0.0:8000`，不是只监听本机 `127.0.0.1`。

继续检查 Ubuntu 防火墙：

```bash
sudo ufw status
```

实际返回：

```text
Status: inactive
```

结论：Ubuntu 本机防火墙没有拦截 8000。

因此当前公网无法访问的原因基本定位为：

```text
腾讯云安全组 / 防火墙入站规则未放行 TCP 8000。
```

需要在腾讯云控制台为该 CVM 实例添加入站规则：

```text
协议：TCP
端口：8000
来源：当前测试机器公网 IP，或临时 0.0.0.0/0
策略：允许
```

注意：`0.0.0.0/0` 只建议短时间测试，后续应限制来源 IP，或改为 Nginx + HTTPS + 更强 API Key。

原始排查清单：

1. 腾讯云安全组是否放行 TCP 8000
2. Ubuntu 防火墙是否放行 8000
3. LiteLLM 是否监听 `0.0.0.0:8000`
4. SSH 反向隧道是否仍在运行
5. LM Studio Server 是否仍在运行

Ubuntu 防火墙检查：

```bash
sudo ufw status
```

如启用了 ufw，可放行：

```bash
sudo ufw allow 8000/tcp
```

## 6. 关于 Claude Code 插件的说明

当前项目主线不需要改协议。

如果目标是让支持 OpenAI-compatible API 的工具调用本地模型，例如：

- Cline
- Roo Code
- Continue
- Cursor 自定义模型
- OpenWebUI
- Cherry Studio
- 自己写的 Python / JS 程序

那么只需要提供：

```text
Base URL + API Key + Model
```

即可。

但 Claude Code 官方 VS Code 插件不是普通 OpenAI-compatible 客户端，它默认使用 Anthropic Claude API 协议。因此它不能简单地只填 OpenAI Base URL。

当前阶段不优先解决 Claude Code 插件协议适配问题，而是先完成通用 OpenAI-compatible API 网关。

## 7. 已出现的问题与解决思路

### 问题 1：5090 没有公网 IP，外部无法直接访问 LM Studio

现象：

```text
外部无法直接访问 172.16.14.240:1234
```

原因：

```text
5090 在校园网 NAT 后面，没有公网端口映射。
```

解决方案：

```text
使用 SSH Reverse Tunnel，把云服务器本机端口反向转发到 5090 本机 LM Studio 端口。
```

### 问题 2：云服务器一开始无法直接作为公网 Base URL

现象：

```text
云服务器能 curl 127.0.0.1:12340，但其他机器还不能直接使用。
```

原因：

```text
127.0.0.1:12340 只监听在云服务器本机回环地址。
```

解决方案：

```text
部署 LiteLLM 监听 0.0.0.0:8000，由 LiteLLM 对外提供 OpenAI-compatible API。
```

### 问题 3：Claude Code 插件是否能直接使用 OpenAI-compatible Base URL

现象：

用户希望保留 Claude Code 插件前端，但后端调用本地 Qwen。

当前判断：

```text
Claude Code 官方插件默认不是 OpenAI-compatible 客户端，不能简单填 LM Studio / LiteLLM 的 OpenAI Base URL。
```

解决方案：

```text
当前先完成通用 OpenAI-compatible API 网关；未来如有需要，再研究 Anthropic-compatible proxy 或协议适配器。
```

## 8. 当前阶段总结与优化建议

### 8.1 当前已完成的最小可用目标

截至目前，项目已经完成最小可用闭环：

```text
外部机器 / VS Code / OpenAI-compatible 客户端
        |
        v
http://82.156.69.153:8000/v1
        |
        v
腾讯云 Ubuntu + LiteLLM
        |
        v
云服务器 127.0.0.1:12340
        |
        v
SSH Reverse Tunnel
        |
        v
5090 Windows + LM Studio :1234
        |
        v
qwen/qwen3.6-27b 等本地模型
```

当前可用配置：

```text
Base URL: http://82.156.69.153:8000/v1
API Key: <OLD_TEST_API_KEY>
Model: qwen-local
```

已验证：

- 云服务器可通过 `127.0.0.1:12340/v1/models` 访问 5090 LM Studio；
- LiteLLM 可通过 `127.0.0.1:8000/v1/models` 暴露模型别名；
- LiteLLM 可通过 `/v1/chat/completions` 成功调用 Qwen；
- 其他机器可通过公网 `82.156.69.153:8000/v1/models` 访问 LiteLLM；
- 腾讯云安全组放行 TCP 8000 后，公网访问问题解决。

### 8.2 当前应优先优化的问题

#### 优化 1：更换临时 API Key

当前 key：

```text
<OLD_TEST_API_KEY>
```

只适合测试，不适合长期公网暴露。建议替换为随机强 key，例如：

```text
sk-labagent-随机长字符串
```

需要同步修改：

- 云服务器 `~/litellm-gateway/config.yaml` 中的 `master_key`
- 各客户端中的 API Key

#### 优化 2：收紧腾讯云安全组来源 IP

如果当前安全组来源是：

```text
0.0.0.0/0
```

表示任意公网 IP 都能访问 8000。短期测试可以，长期不建议。

建议改为：

```text
当前常用公网 IP/32
```

如果经常换网络，可暂时保留公网开放，但必须尽快完成强 key、HTTPS、访问日志等保护。

#### 优化 3：让 LiteLLM 后台常驻运行

当前 LiteLLM 是在 SSH 终端里手动启动：

```bash
litellm --config config.yaml --host 0.0.0.0 --port 8000
```

问题：终端关闭后服务可能停止。

建议下一步改成 systemd 服务：

```text
litellm-gateway.service
```

这样云服务器重启后可以自动恢复。

#### 优化 4：让 SSH 反向隧道自动重连

当前 SSH Reverse Tunnel 也是手动运行：

```bash
ssh -N -R 12340:127.0.0.1:1234 ubuntu@82.156.69.153
```

问题：网络波动、PowerShell 关闭、Windows 重启都会中断隧道。

建议下一步使用：

- Windows 任务计划程序；或
- `autossh` 类似机制；或
- PowerShell 循环脚本；

让 5090 自动维持反向隧道。

#### 优化 5：处理 Qwen reasoning_content 泄露

当前响应中会返回大量 reasoning / Thinking Process 内容。

影响：

- 输出体积大；
- token 消耗高；
- 客户端体验差；
- 对外服务时不够干净。

建议后续在 LM Studio 模型设置、LiteLLM 配置或客户端侧尝试关闭 / 过滤 reasoning 内容。

#### 优化 6：后续引入 Nginx + HTTPS

当前公网地址是：

```text
http://82.156.69.153:8000/v1
```

后续建议升级为：

```text
https://api.example.com/v1
```

收益：

- HTTPS 加密；
- 更适合接入客户端；
- 可以加访问日志、限流、反代规则；
- 简历项目表达更完整。

### 8.3 推荐下一步执行顺序

建议不要马上上 vLLM，先把当前链路稳定化：

1. 更换 LiteLLM 强 API Key；
2. 把 LiteLLM 配成 systemd 后台服务；
3. 把 SSH 反向隧道做成自动重连；
4. 用 Cline / Roo Code / Continue 任一客户端真实接入测试；
5. 处理 Qwen reasoning 输出问题；
6. 再考虑 Nginx + HTTPS；
7. 最后再做 LM Studio -> vLLM 的推理服务升级。

## 9. 优化 1：更换强 API Key（已完成）

### 9.1 原因

原测试 key：

```text
<OLD_TEST_API_KEY>
```

过于简单，且公网裸奔，存在安全风险。

### 9.2 执行步骤

生成随机强 key：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

实际输出：

```text
<LABAGENT_API_KEY>
```

更新配置文件：

```bash
nano ~/litellm-gateway/config.yaml
```

将 `master_key` 替换为新生成的强 key。

重启 LiteLLM 后验证：

```bash
curl http://127.0.0.1:8000/v1/models -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

成功返回模型列表，新 key 生效。

### 9.3 待办

所有客户端（5090 本机、其他机器）中的 API Key 需要同步更新。

## 10. 优化 2：LiteLLM 配置为 systemd 后台常驻服务（已完成）

### 10.1 原因

此前 LiteLLM 在终端手动启动，SSH 断开或终端关闭后服务停止。

### 10.2 执行步骤

创建服务文件：

```bash
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
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable litellm-gateway
sudo systemctl start litellm-gateway
```

验证状态：

```bash
sudo systemctl status litellm-gateway
```

实际返回 `active (running)`，服务启动成功。

### 10.3 验证结果

```bash
curl http://127.0.0.1:8000/v1/models -H "Authorization: Bearer <LABAGENT_API_KEY>"
```

返回模型列表，systemd 服务运行正常。

### 10.4 常用管理命令

```bash
# 查看状态
sudo systemctl status litellm-gateway

# 重启（修改 config.yaml 后需要重启）
sudo systemctl restart litellm-gateway

# 查看日志
sudo journalctl -u litellm-gateway -f

# 停止
sudo systemctl stop litellm-gateway
```

## 11. 优化 3：SSH 反向隧道自动重连

### 11.1 原因

当前 SSH 反向隧道是 5090 本机手动运行：

```bash
ssh -N -R 12340:127.0.0.1:1234 ubuntu@82.156.69.153
```

问题：

- PowerShell 关闭后隧道断开
- 网络波动后隧道不会自动恢复
- Windows 重启后需要手动重连

### 11.2 方案

在 5090 本机创建一个 PowerShell 脚本 `auto_tunnel.ps1`，循环运行：

```powershell
while ($true) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Starting SSH tunnel..."
    ssh -N -R 12340:127.0.0.1:1234 ubuntu@82.156.69.153
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Tunnel disconnected. Reconnecting in 5 seconds..."
    Start-Sleep -Seconds 5
}
```

使用方式：

```powershell
powershell -ExecutionPolicy Bypass -File auto_tunnel.ps1
```

### 11.3 如果需要开机自动启动

可以将脚本加入 Windows 任务计划程序：

```text
触发器：用户登录时
操作：powershell -ExecutionPolicy Bypass -File C:\path\to\auto_tunnel.ps1
```

或者将快捷方式放入启动文件夹：

```text
shell:startup
```

## 12. 优化 3：SSH 反向隧道自动重连（已完成）

### 12.1 原因

此前 SSH 反向隧道手动运行，断开后不会自动恢复。

### 12.2 遇到的问题

首次启动 `auto_tunnel.ps1` 时报错：

```text
Warning: remote port forwarding failed for listen port 12340
```

原因：旧的 SSH 会话仍占用云服务器 12340 端口。

解决方案：在云服务器执行 `sudo fuser -k 12340/tcp` 释放端口，然后重启脚本。

### 12.3 验证结果

在 5090 本机启动 `auto_tunnel.ps1`，隧道连接成功。

在 David 机器验证公网访问：

```powershell
Invoke-RestMethod -Uri "http://82.156.69.153:8000/v1/models" -Headers @{ Authorization = "Bearer <LABAGENT_API_KEY>" }
```

成功返回模型列表，公网 API 访问正常。

### 12.4 当前完整链路状态

```text
5090 auto_tunnel.ps1 (后台常驻)
        ↓
SSH Reverse Tunnel :12340
        ↓
Cloud Server LiteLLM systemd (开机自启)
        ↓
http://82.156.69.153:8000/v1
        ↓
任何支持 OpenAI-compatible API 的客户端
```

所有组件均已后台运行/自动重连，无需手动维护。

## 13. 优化 4：SSH 密钥认证（已完成）

### 13.1 原因

每次 SSH 隧道重连都需要输入密码，不适合自动重连脚本。

### 13.2 执行步骤

在 5090 本机生成密钥：

```powershell
ssh-keygen -t ed25519
```

一路回车，不设 passphrase。

将公钥传到云服务器：

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh ubuntu@82.156.69.153 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

验证免密登录：

```powershell
ssh ubuntu@82.156.69.153 "echo ok"
```

返回 `ok` 且无密码提示，认证成功。

### 13.3 验证结果

`auto_tunnel.ps1` 重启后直接连上，不再弹出密码输入。

## 14. 优化 5：auto_tunnel.ps1 改进（已完成）

### 14.1 原因

原脚本存在两个问题：

- SSH 空闲后自动断开，脚本不感知（假死）
- 没有心跳保活机制

### 14.2 改进内容

```powershell
while ($true) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] Starting SSH tunnel to cloud server..."
    ssh -N -R 12340:127.0.0.1:1234 `
        -o ServerAliveInterval=60 `
        -o ServerAliveCountMax=3 `
        -o ConnectTimeout=10 `
        ubuntu@82.156.69.153
    $exitCode = $LASTEXITCODE
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$timestamp] Tunnel disconnected (exit code: $exitCode). Reconnecting in 5 seconds..."
    Start-Sleep -Seconds 5
}
```

关键参数：

- `ServerAliveInterval=60` — 每 60 秒发心跳
- `ServerAliveCountMax=3` — 3 次无回应才断开
- `ConnectTimeout=10` — 连接超时 10 秒
- `$LASTEXITCODE` — 记录退出码方便排查

## 15. 优化 6：Cline 客户端接入测试（已完成）

### 15.1 Cline 安装

在 VS Code 扩展商店安装 Cline 插件。

### 15.2 Cline 配置

```text
API Provider: OpenAI Compatible
Base URL: http://82.156.69.153:8000/v1
API Key: <LABAGENT_API_KEY>
Model ID: qwen-local
```

### 15.3 测试结果

在 Cline 中输入"帮我看看当前项目的文件结构"，Cline 成功：

- 读取项目文件夹
- 列出完整文件树
- 显示 Task Completed

### 15.4 遇到的问题

首次测试时 SSH 隧道已断开，Cline 报 500 错误。重启 `auto_tunnel.ps1` 后 Cline 自动重试成功。

### 15.5 当前完整链路

```text
Cline (VS Code 插件)
    ↓
http://82.156.69.153:8000/v1
    ↓
LiteLLM (systemd 后台服务)
    ↓
SSH Reverse Tunnel (auto_tunnel.ps1 自动重连 + 心跳保活)
    ↓
5090 LM Studio → qwen/qwen3.6-27b
```

## 16. 简历表达草稿

可以后续整理成如下项目描述：

> 设计并搭建一套基于本地高性能 GPU 与云服务器中转的私有 AI API 网关。通过 SSH Reverse Tunnel 解决校园网 NAT 环境下本地 RTX 5090 推理节点无法公网访问的问题，并使用 LiteLLM 将 LM Studio / 本地大模型包装为 OpenAI-compatible API，支持远程客户端、Agent 工具和多模型服务接入。项目后续规划接入 vLLM、Nginx、HTTPS、多模态节点与统一模型调度能力。

可强调的技术点：

- 本地大模型部署
- OpenAI-compatible API
- SSH Reverse Tunnel
- LiteLLM API Gateway
- NAT 网络约束处理
- 多节点 AI Infra 架构
- 远程模型服务暴露
- Agent 工具链集成

## 9. 后续记录规则

后续每次进行配置、调试、验证或遇到错误时，都应该更新本文档，至少记录：

1. 做了什么
2. 为什么做
3. 执行了什么命令
4. 出现了什么问题
5. 如何解决
6. 当前状态是否通过验证
7. 对简历或项目复盘有什么价值


