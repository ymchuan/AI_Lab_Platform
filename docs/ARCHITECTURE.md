# 架构设计

## 系统概览

LabAgent Platform 是一个私有 AI 基础设施平台，将内网 GPU 主机的推理能力通过云服务器暴露为标准化 API 服务。

当前事实基线（2026-06-18 校准）：

- 5090 主机已接入 LM Studio，并完成 `qwen/qwen3.6-27b`、`qwen/qwen3-coder-30b`、`qwen/qwen3-30b-a3b-2507`、`qwen/qwen3.6-35b-a3b`、`google/gemma-4-31b`、`zai-org/glm-4.7-flash`、`text-embedding-nomic-embed-text-v1.5` 等本地候选模型评测。
- 5090 上的默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` 降为 `qwen-think` reasoning baseline。
- 新设备硬件已校准为 RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 + 61.4GB RAM，已通过 `:12341` SSH 反向隧道接入 `embed-local` embedding 路由。
- 8060S 当前无法使用，冻结近期接入计划。
- SSH 反向隧道不是常驻状态，需要在 5090 手动开启；未开启时公网 chat completion 失败是预期状态。
- 云服务器为 Ubuntu 24.04，2 核 2GB，短期无法升级，后续只承担轻量 API 网关、鉴权、HTTPS 入口和 SSH 隧道中转。
- OpenWebUI、RAG、Agent Runtime、向量数据库、评测任务等重服务应部署到本地 GPU 主机，而不是云服务器。
- 新设备专用显存可按资源池理解为 RTX 5080 16GB + RTX 4060 Ti 16GB = 32GB，但不是单个连续 32GB 显存；Windows 显示的 GPU 总内存包含 shared system memory，不能当作 VRAM。单模型跨卡需要推理引擎支持 tensor parallel、pipeline parallel、layer offload 或手动分层。
- RAG Service v1 已新增：`services/rag` 使用项目 Markdown 文档、`embed-local`、本地 JSON 向量索引和 `qwen-agent`，实现 CLI 检索、带引用回答和零依赖 HTTP API。下一步接入向量数据库、reranker 和 answer eval，而不是部署到 2GB 云服务器。

## 架构图

```text
┌──────────────────────────────────────────────────────────────┐
│ 客户端层                                                       │
│ Cline / OpenWebUI / Cursor / 自定义 Agent / Python / JS        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ 云服务器：Ubuntu 24.04 · 2核 · 2GB                             │
│                                                              │
│ LiteLLM API Gateway (:8000)                                  │
│ - API Key 认证                                                │
│ - OpenAI-compatible API                                      │
│ - 模型别名路由：qwen-local / qwen-agent / embed-local              │
│ - systemd 后台运行 + 崩溃重启                                  │
│                                                              │
│ SSH Reverse Tunnels                                          │
│ - :12340 -> 5090:1234    手动开启                              │
│ - :12341 -> 新设备:1234  Nomic embedding                       │
│                                                              │
│ 约束：2GB 内存，不适合作为 RAG / Agent / OpenWebUI 常驻节点     │
└──────────────────────────────┬───────────────────────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
┌──────────────────┐                      ┌──────────────────┐
│ 5090 主机         │                      │ 新设备            │
│ RTX 5090 32GB     │                      │ RTX 5080 16GB     │
│ 93.7GB RAM        │                      │ RTX 4060 Ti 16GB  │
│ LM Studio         │                      │ 61.4GB RAM        │
│ 本地候选模型池    │                      │ LM Studio         │
│ ✅ 已部署         │                      │ ✅ Embedding 已接入 │
└──────────────────┘                      └──────────────────┘

8060S 当前无法使用，暂不作为近期计算节点。
```

## 设计决策

### 为什么用 SSH Reverse Tunnel

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| SSH Reverse Tunnel | 零额外依赖，SSH 内置 | 需要维护连接 | ✅ 当前方案 |
| FRP | 稳定，功能丰富 | 额外软件，可能被管理员视为内网穿透 | ❌ 暂不采用 |
| Tailscale / ZeroTier | 配置简单 | 可能被归类为 VPN | ❌ 暂不采用 |

### 为什么用 LiteLLM

1. API Key 认证：LM Studio 默认不适合直接暴露公网。
2. 模型别名：对外暴露 `qwen-local`，隐藏真实模型名和节点细节。
3. 多后端：未来优先接入 5090 和 5080 新设备；8060S 暂时冻结。
4. 统一入口：所有客户端只需要一个 Base URL。

### 为什么云服务器只做轻量控制面

云服务器只有 2GB 内存，且短期无法升级。OpenWebUI 约占 900MB，LiteLLM 约占 250MB，再加 SSH、系统进程和日志，很容易 OOM。

后续策略：

1. 云服务器只保留 LiteLLM、SSH 隧道中转、HTTPS 入口和访问控制。
2. OpenWebUI、RAG Pipeline、Agent Runtime、向量数据库等重服务迁移到本地 GPU 主机。
3. 对外仍保持一个公网 Base URL，内部由 LiteLLM / 反向代理路由到不同本地节点。

## 节点分工规划

```text
5090 (RTX 5090 32GB)        -> 主力模型推理 / 代码模型 / Agent 主模型
新设备 (RTX 5080 16GB)      -> VL / 中等代码模型 / Reranker 候选
新设备 RTX 4060 Ti 16GB     -> 当前 Embedding / 轻量模型 / Reranker / 实验任务
云服务器 (2GB)               -> LiteLLM / HTTPS / 鉴权 / SSH 隧道中转

8060S 当前不可用，OCR / Whisper / 文档解析计划后移到新设备或后续新节点。
```

## 数据流

```text
1. 用户在 Cline 输入任务
2. Cline 构造 OpenAI 格式请求
3. POST http://82.156.69.153:8000/v1/chat/completions
4. LiteLLM 验证 API Key
5. LiteLLM 路由到 qwen-local / qwen-agent / embed-local 后端
6. 请求通过 SSH :12340 转发到 5090:1234（前提：5090 已手动开启反向隧道）
7. LM Studio 调用当前默认 `qwen/qwen3-coder-30b` 模型推理
8. 响应原路返回
```

Embedding 请求的数据流：

```text
1. RAG / 客户端请求 POST /v1/embeddings，model=embed-local
2. LiteLLM 验证 API Key
3. 请求通过 SSH :12341 转发到新设备 127.0.0.1:1234
4. 新设备 LM Studio 调用 `text-embedding-nomic-embed-text-v1.5-embedding`
5. 返回 768 维向量
```

RAG v0 请求的数据流：

```text
1. 本地执行 python -m services.rag.cli index
2. 读取 README.md / HANDOFF.md / docs/*.md
3. Markdown 文档按标题和长度切成 chunks
4. 每个 chunk 通过公网 LiteLLM 调用 embed-local 生成 768 维向量
5. 本地保存 data/rag/index.json
6. 用户执行 search/ask 时，问题先转成向量，再用 cosine similarity 检索 top-k chunks
7. ask 把 [S1] / [S2] 证据块交给 qwen-agent 生成带引用回答
```

RAG Service v1 远程请求的数据流：

```text
1. David/Cline 请求 http://82.156.69.153:18010/v1/rag/ask
2. 云服务器 SSH reverse tunnel 转发到 5090:8010
3. 5090 RAG Service 读取本地 data/rag/index.json
4. RAG Service 调用公网 LiteLLM 的 embed-local 做 query embedding
5. 本地检索 top-k chunks
6. RAG Service 调用公网 LiteLLM 的 qwen-agent 生成带引用回答
7. 答案和 sources 返回 David/Cline
```

## 扩展路线

### Phase 1（当前）✅

- [x] 5090 LM Studio + `qwen/qwen3.6-27b` GGUF Q6_K
- [x] SSH Reverse Tunnel + 密钥认证（当前手动开启，不是常驻）
- [x] LiteLLM API Gateway（systemd）
- [x] Cline 客户端接入
- [x] OpenWebUI 初步部署
- [x] SSH 双向心跳保活
- [x] 云服务器攻击后恢复

### Phase 2（近期）

- [x] 5090 默认 Agent/Cline 模型定为 `qwen/qwen3-coder-30b`
- [x] 新设备 `embed-local` v1 接入：LM Studio + Nomic Embed Text v1.5 + SSH `:12341` + LiteLLM 路由
- [ ] 调研并确定 5080 新设备的 Reranker / VL / 第二代码模型组合
- [x] 建立本地 benchmark v2：网关健康、吞吐、首 token 延迟、Agent 任务、RAG oracle、repo map、patch、Cline 多轮对话
- [x] LiteLLM 多节点基础路由：`qwen-local` / `qwen-agent` / `embed-local`
- [x] RAG v0：Markdown chunking + `embed-local` + 本地 JSON index + retrieval benchmark + cited answer
- [ ] 云服务器轻量 HTTPS 入口（Nginx 或 Caddy）

### Phase 3（项目深度）

- [x] RAG Service v1：零依赖 HTTP API，支持本地 / David 远程调试
- [ ] RAG v1.x：向量数据库、reranker、answer eval、文档上传
- [ ] Agent 开发框架
- [ ] MCP Server
- [ ] Skills / Tools 插件体系
- [ ] Eval Harness / Agent Benchmark
- [ ] LoRA 微调 / GGUF 或 AWQ 量化实验
- [ ] vLLM 或 SGLang 替代 LM Studio
- [ ] 监控和可观测性
