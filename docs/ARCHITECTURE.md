# 架构设计

## 系统概览

LabAgent Platform 是一个私有 AI 基础设施平台，将内网 GPU 主机的推理能力通过云服务器暴露为标准化 API 服务。

当前事实基线（2026-06-15 校准）：

- 5090 主机已部署 `qwen/qwen3.6-27b` 本地模型；文件为 `Qwen3.6-27B-Q6_K.gguf`，格式 GGUF，量化 Q6_K，大小约 23.01GB。
- 4090D 新设备尚未部署模型、隧道或 LiteLLM 路由。
- 8060S 当前无法使用，冻结近期接入计划。
- SSH 反向隧道不是常驻状态，需要在 5090 手动开启；未开启时公网 chat completion 失败是预期状态。
- 云服务器为 Ubuntu 24.04，2 核 2GB，短期无法升级，后续只承担轻量 API 网关、鉴权、HTTPS 入口和 SSH 隧道中转。
- OpenWebUI、RAG、Agent Runtime、向量数据库、评测任务等重服务应部署到本地 GPU 主机，而不是云服务器。
- 新设备显存可按资源池理解为 4090D 24GB + 4060 Ti 16GB = 40GB，但不是单个连续 40GB 显存；单模型跨卡需要推理引擎支持 tensor parallel、pipeline parallel、layer offload 或手动分层。

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
│ - 模型别名路由：qwen-local -> 5090 当前 qwen/qwen3.6-27b 后端          │
│ - systemd 后台运行 + 崩溃重启                                  │
│                                                              │
│ SSH Reverse Tunnels                                          │
│ - :12340 -> 5090:1234    手动开启                              │
│ - :12341 -> 新设备:1234  待接入                               │
│                                                              │
│ 约束：2GB 内存，不适合作为 RAG / Agent / OpenWebUI 常驻节点     │
└──────────────────────────────┬───────────────────────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
┌──────────────────┐                      ┌──────────────────┐
│ 5090 主机         │                      │ 新设备            │
│ RTX 5090 32GB     │                      │ RTX 4090D 24GB    │
│ 93.7GB RAM        │                      │ RTX 4060 Ti 16GB  │
│ LM Studio         │                      │ 61.6GB RAM        │
│ qwen/qwen3.6-27b │                      │ 未接入            │
│ ✅ 已部署         │                      │ ⏳ 待选型/部署     │
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
3. 多后端：未来优先接入 5090 和 4090D 新设备；8060S 暂时冻结。
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
新设备 (RTX 4090D 24GB)     -> 第二推理节点 / 中等代码模型 / Reranker
新设备 RTX 4060 Ti 16GB     -> Embedding / 轻量模型 / Reranker / 实验任务
云服务器 (2GB)               -> LiteLLM / HTTPS / 鉴权 / SSH 隧道中转

8060S 当前不可用，OCR / Whisper / 文档解析计划后移到新设备或后续新节点。
```

## 数据流

```text
1. 用户在 Cline 输入任务
2. Cline 构造 OpenAI 格式请求
3. POST http://82.156.69.153:8000/v1/chat/completions
4. LiteLLM 验证 API Key
5. LiteLLM 路由到 qwen-local 后端
6. 请求通过 SSH :12340 转发到 5090:1234（前提：5090 已手动开启反向隧道）
7. LM Studio 调用当前 `qwen/qwen3.6-27b` GGUF Q6_K 模型推理
8. 响应原路返回
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

- [ ] 调研并确定 5090 / 4090D 新设备的模型组合
- [x] 建立本地 benchmark v2：网关健康、吞吐、首 token 延迟、Agent 任务、RAG oracle、repo map、patch、Cline 多轮对话
- [ ] 新设备接入：推理服务 + SSH 隧道 :12341 + LiteLLM 路由
- [ ] LiteLLM 多节点模型路由
- [ ] 云服务器轻量 HTTPS 入口（Nginx 或 Caddy）

### Phase 3（项目深度）

- [ ] RAG 知识库系统
- [ ] Agent 开发框架
- [ ] MCP Server
- [ ] Skills / Tools 插件体系
- [ ] Eval Harness / Agent Benchmark
- [ ] LoRA 微调 / GGUF 或 AWQ 量化实验
- [ ] vLLM 或 SGLang 替代 LM Studio
- [ ] 监控和可观测性

