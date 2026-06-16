# 故障排查

## 问题 1：SSH 隧道断开（最常见）

**症状**：Cline/OpenWebUI 报 502 或 Connection error

**排查**：

```bash
# 在云服务器检查
ss -tlnp | grep :12340
curl http://127.0.0.1:12340/v1/models
```

**常见原因**：

1. **服务器内存不足**（最常见）— 云服务器只有 2GB，OpenWebUI 占约 900MB，容易导致 OOM

```bash
# 检查内存
free -h
# 如果可用内存 < 200MB，杀掉 OpenWebUI
pkill -f open-webui
```

2. **端口被占用**

```bash
sudo fuser -k 12340/tcp
```

3. **云服务器 SSH 未配置保活**

```bash
sudo sed -i 's/#ClientAliveInterval 0/ClientAliveInterval 30/' /etc/ssh/sshd_config
sudo sed -i 's/#ClientAliveCountMax 3/ClientAliveCountMax 10/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

**恢复**：在 5090 本机重新建立隧道

```powershell
ssh -N -R 12340:127.0.0.1:1234 -i C:\Users\N\.ssh\id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

## 问题 2：公网无法访问 8000 端口

**症状**：`Invoke-RestMethod : 远程服务器返回错误: (502)`

**排查**：

```bash
ss -tlnp | grep :8000
# 应该显示 0.0.0.0:8000
sudo ufw status
```

**解决方案**：腾讯云控制台安全组添加 TCP 8000 入站规则

## 问题 3：PowerShell curl 报错

**症状**：`无法绑定参数"Headers"`

**解决方案**：

```powershell
# 使用 Invoke-RestMethod
Invoke-RestMethod -Uri "http://82.156.69.153:8000/v1/models" -Headers @{ Authorization = "Bearer <Key>" }

# 或使用真正的 curl
curl.exe http://82.156.69.153:8000/v1/models -H "Authorization: Bearer <Key>"
```

## 问题 4：Cline 报 500 Connection Error

**症状**：Cline 能列出模型但聊天报错

**排查**：测试 chat 接口

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer <Key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-local","messages":[{"role":"user","content":"hi"}],"max_tokens":50}'
```

**常见原因**：SSH 隧道未开启或断开（最常见）

**2026-06-15 现场记录**：

- `GET /v1/models` 可以返回 `qwen-local`。
- `POST /v1/chat/completions` 返回 HTTP 500。
- LiteLLM 错误信息为：`OpenAIException - Connection error`。
- 直接访问 LM Studio 本机 `http://127.0.0.1:1234/v1` 可以列出模型并完成 chat 请求。
- 用户确认当时没有开启 5090 SSH 反向隧道，因此公网 chat 失败是预期状态。

这说明当前更像是 **云端 LiteLLM -> SSH 隧道 -> LM Studio upstream** 的连接状态问题，而不是模型文件损坏。排查顺序：

```bash
# 云服务器
curl http://127.0.0.1:12340/v1/models
curl http://127.0.0.1:12340/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen/qwen3.6-27b","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'

sudo journalctl -u litellm-gateway -n 100 --no-pager
```

如果云服务器无法通过 `127.0.0.1:12340` 调通 chat，则重建 5090 反向隧道；如果 `12340` 正常但 LiteLLM 报错，则检查 LiteLLM `config.yaml` 中的 `api_base`、`model` 和超时配置。

## 问题 5：5090 本机访问公网 API 报 502

**原因**：NAT 回环 — 校园网不支持内网机器通过公网 IP 访问自己

**解决方案**：5090 本机直接连 `http://127.0.0.1:1234/v1`

## 问题 6：Qwen 返回大量 Thinking Process / `message.content` 为空

**症状**：

- 响应中 `reasoning_content` 很长。
- `message.content` 可能为空。
- `finish_reason=length`，说明输出预算在 thinking 阶段就被耗尽。
- Benchmark 中 Agent 任务可能请求成功但评分失败。

**验证方式**：

```powershell
python benchmarks/model_latency.py --stream
python benchmarks/model_latency.py --stream --no-think
```

**当前发现**：

`/no_think` 对当前 LM Studio + LiteLLM 路径没有明显效果，raw 和 no-think 两组 benchmark 都仍然产生大量 `reasoning_content`。

2026-06-15 直连 LM Studio 复测后，当前 `qwen/qwen3.6-27b` preset 仍不适合作为 Agent 主执行模型：

- model latency：4/4 请求成功，但 4/4 `finish_reason=length`，平均 `content` 长度为 0。
- agent tasks：0/3 通过。
- RAG oracle：1/3 通过。
- 判断：保留为 `qwen-think` 深度分析候选，另选 output-stable 的 instruct/coder 模型做 `qwen-agent`。

**后续处理方向**：

1. 在 LM Studio 检查模型模板、thinking/reasoning 开关和 stop 配置。
2. 尝试更适合 OpenAI-compatible agent 客户端的 instruct/coder 模型。
3. 在 LiteLLM 或代理层过滤 `reasoning_content`，只返回最终 `content`。
4. Benchmark 脚本已记录 `content`、`reasoning_content` 和 `finish_reason`，可用于对比修复效果。

## 问题 7：OpenWebUI 启动报 Embedding 错误或占用过高

**症状**：`ValueError: No embedding model is loaded`

**原因**：云服务器无法访问 HuggingFace，或 2GB 内存不足以稳定承载 OpenWebUI + LiteLLM。

**解决方案**：

```bash
RAG_EMBEDDING_ENGINE=openai RAG_EMBEDDING_MODEL=qwen-local open-webui serve --port 3000
```

长期方案：把 OpenWebUI 迁移到 5090 或新设备，云服务器只保留 LiteLLM / HTTPS / SSH 隧道。

## 问题 8：云服务器被攻击后恢复

**步骤**：

```text
1. SSH 连接（先 ssh-keygen -R 清除旧指纹）
2. 上传 5090 公钥
3. 安装 Python 3.12 + pip + venv
4. 安装 LiteLLM + 创建配置文件
5. 配置 systemd 服务
6. 配置 SSH 保活（ClientAliveInterval=30）
7. 安全组放行 8000
8. 5090 建立 SSH 隧道
9. 验证全链路
10. 按需启动 OpenWebUI，或迁移到本地节点
```

