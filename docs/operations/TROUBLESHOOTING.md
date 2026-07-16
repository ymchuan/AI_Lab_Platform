# 故障排查

## 问题 1：SSH 隧道断开（最常见）

**症状**：Cline/OpenWebUI 报 502 或 Connection error

**排查**：

```bash
# 在云服务器检查
ss -tlnp | grep :12340
curl http://127.0.0.1:12340/v1/models
ss -tlnp | grep :12341
curl http://127.0.0.1:12341/v1/models
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

新设备 embedding 隧道恢复：

```powershell
ssh -N -R 12341:127.0.0.1:1234 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
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
RAG_EMBEDDING_ENGINE=openai RAG_EMBEDDING_MODEL=embed-local open-webui serve --port 3000
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

## 问题 9：LM Studio 显示 localhost 还是 172.16.x.x

**现象**：

- LM Studio 显示 `http://127.0.0.1:1234`：服务只监听本机。
- LM Studio 显示 `http://172.16.14.x:1234`：已开启 `Serve on Local Network`，同一内网机器可能直接访问。

**建议**：

正式架构优先保持 localhost，只通过 SSH 反向隧道接入云服务器：

```text
5090:   云服务器 :12340 -> 5090 127.0.0.1:1234
新设备: 云服务器 :12341 -> 新设备 127.0.0.1:1234
```

这样外部客户端只能通过 LiteLLM API Key 访问，不会绕过网关。只有临时调试内网互通时才打开 `Serve on Local Network`，并建议用 Windows 防火墙限制来源 IP。

## 问题 10：PowerShell curl 发送 JSON 到 embeddings 失败

**症状**：

```text
Invalid body: failed to parse JSON value
curl: (3) URL rejected
```

**原因**：PowerShell 的引号和反斜杠转义把 JSON 拆坏。

**解决**：

```powershell
curl.exe http://127.0.0.1:1234/v1/embeddings `
  -H "Content-Type: application/json" `
  --data-raw '{ "model": "text-embedding-nomic-embed-text-v1.5-embedding", "input": "hello labagent" }'
```

或使用原生命令：

```powershell
$body = @{
  model = "text-embedding-nomic-embed-text-v1.5-embedding"
  input = "hello labagent"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:1234/v1/embeddings" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## 问题 11：Codex / labagent-agent 文本可用，但图片识别失败

**症状**：

- Codex 通过 `labagent-agent` 能正常回答文本问题。
- `/v1/responses stream=true` 已返回 `response.completed`。
- 发送图片后，最终回答提示 `vision-local` 或 `embed-local` 连接错误。
- LiteLLM `/v1/models` 仍能看到 `vision-local`，但真正图片请求失败。

**判断**：

这通常不是 Codex 协议问题，也不是 `labagent-agent` 的 18020 公网入口问题，而是新设备到云服务器的 `:12341` 反向隧道没有运行。`vision-local` 和 `embed-local` 都挂在新设备 LM Studio 后面，所以 `:12341` 断开时两者会一起失败。

**排查**：

```bash
# 云服务器上检查
ss -ltnp | grep :12341
curl -sS -m 5 http://127.0.0.1:12341/v1/models
```

如果 `ss` 看不到 `:12341`，或者 `curl` 显示无法连接，就说明新设备隧道没开。

**恢复**：

在新设备 PowerShell 中确认 LM Studio 已启动，并 load 了 embedding / vision 模型，然后重新开启：

```powershell
ssh -N -R 12341:127.0.0.1:1234 `
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 `
  ubuntu@82.156.69.153
```

恢复后再从 5090 或云服务器验证：

```powershell
curl.exe http://82.156.69.153:8000/v1/embeddings `
  -H "Authorization: Bearer <LABAGENT_API_KEY>" `
  -H "Content-Type: application/json" `
  --data-raw '{ "model": "embed-local", "input": "hello" }'
```

如果 embedding 恢复，`vision-local` 图片请求才有继续测试的意义。

## 问题 12：8060S benchmark 脚本出现乱码和 ParserError

**症状**：

- `run_8060s_brain_smoke.ps1` 中的中文变成 `鍊欓...` 一类乱码。
- PowerShell 报 `UnexpectedToken`、`哈希文本不完整` 或缺少右括号。
- 错误发生在请求模型之前。

**原因**：

旧版脚本源码包含中文 prompt。Windows PowerShell 5.1 可能把无 BOM UTF-8 文件按系统代码页读取；文件经过编辑器或聊天工具再次保存后，乱码可能进一步破坏字符串边界。该故障与 LM Studio、模型 ID 和推理能力无关。

**解决**：

1. 删除或覆盖 8060S 上已经乱码的旧副本，不要在乱码文件里逐行修补。
2. 从当前仓库重新复制 `benchmarks/run_8060s_brain_smoke.ps1`。
3. 当前脚本源码保持 ASCII-only，中文输出要求由英文 prompt 表达，兼容 Windows PowerShell 5.1 和 PowerShell 7。
4. 重新运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\run_8060s_brain_smoke.ps1 `
  -Model "qwen3.6-35b-a3b-uncensored" `
  -TimeoutSec 600 `
  -MaxTokens 512 `
  -SkipVision
```

如果仍在脚本解析阶段失败，先确认文件不是旧副本：

```powershell
Select-String -Path .\run_8060s_brain_smoke.ps1 -Pattern "鍊|妯|€"
```

当前版本应当没有任何匹配。

## 问题 13：8060S `/v1/models` 成功，但所有 chat 都返回 HTTP 400

**症状**：

- `GET /v1/models` 返回多个模型 ID。
- `POST /v1/chat/completions` 在等待几十秒后返回 HTTP 400。
- 报告中 `content`、`reasoning` 和 token 计数全部为 0。

**判断**：

这不是模型回答质量差，而是请求在生成前被 LM Studio 拒绝。`/v1/models` 可能返回本机模型库存，不能单独证明指定 ID 已作为运行实例加载。常见原因包括选错当前加载 ID、JIT load 失败、内存/上下文配置无法加载，或后端返回了具体请求错误。

2026-07-15 8060S 实例中，增强报告捕获到：

```text
The model has crashed without additional information.
Exit code: 18446744072635812000
Model reloaded.
```

2026-07-16 又用 Q4 `qwen3.6-35b-a3b@q4_k_m` 复测，实际生成仍为 0/5，第一次短请求即以相同退出码崩溃。旧版脚本在 fatal 错误后继续发送剩余 case，所以后面的 `Model reloaded.` / channel error 包含自动重载期间的连锁失败。当前脚本已改为最小 preflight 失败后停止，避免重复撞击正在重载的 runtime。单纯从 Q8 换成 Q4 没有让最小请求成功，但不要仅凭退出码把根因写成 OOM；还需要用 LM Studio 日志、保守加载参数和更小模型对照定位。

同一修复版脚本在 5090 的 `qwen/qwen3-coder-30b` 上完成 5/5 文本生成，说明请求 schema 和 harness 可以正常工作。这个跨机器控制组只能排除“脚本对所有 LM Studio 实例都会触发 channel error”，不能区分 8060S 的 35B 模型配置与 AMD runtime；需要在 8060S 上换更小模型继续控制变量。

修复版脚本在 8060S 的 run `20260716_173515` 中只发送一次最小 preflight，准确已加载的 35B Q4 仍返回 `Model reloaded.`，其余 case 均按设计跳过。此时先把 LM Studio 的 Parallel Requests 从 4 降到 1，卸载并重新加载模型后重试；若最小请求仍失败，不再重复 35B 全套 smoke，改测 12B。12B 成功说明应继续定位 35B 模型/资源/offload，12B 也失败则优先定位 LM Studio runtime、AMD 后端或驱动。

**排查**：

1. 在 LM Studio UI 确认 Developer / Local Server 当前真正加载的模型；如果已安装 LM Studio CLI，也可运行 `lms ps`。
2. 查看 LM Studio server/runtime 日志，保存崩溃前最后 50-100 行。
3. 将 context length 先固定为 4096，关闭 speculative decoding，降低 KV cache / GPU offload 等资源压力后重载。
4. 不再继续尝试其他 35B 量化作为第一优先级。先跑一个更小的同机对照模型，例如已安装的 27B IQ3_XS 或 12B；若小模型可用而 35B 崩溃，优先定位 35B 资源/量化配置。若小模型也崩溃，优先定位运行时、驱动或 AMD 后端。
5. 用当前版 `run_8060s_brain_smoke.ps1` 复测；它会优先保存 PowerShell 的 `ErrorDetails.Message`。
6. 如果仍失败，先单独发一个最小请求并查看错误正文：

```powershell
$body = @{
  model = "<LM Studio 当前加载的准确模型 ID>"
  messages = @(@{ role = "user"; content = "Reply exactly: brain-ok" })
  max_tokens = 64
  temperature = 0
} | ConvertTo-Json -Depth 10

try {
  Invoke-RestMethod `
    -Uri "http://127.0.0.1:1234/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $body `
    -TimeoutSec 600
} catch {
  $_.Exception.Message
  $_.ErrorDetails.Message
}
```

只有最小 chat 返回正常 `content` 后，才继续整套 smoke、`:12342` 隧道和 LiteLLM alias。

