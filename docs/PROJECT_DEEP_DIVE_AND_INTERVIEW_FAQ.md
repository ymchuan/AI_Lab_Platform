# LabAgent 项目深挖与面试 FAQ

> 目标读者：项目作者本人、秋招面试官、新接手的 AI / 工程同学。
>
> 目标：把 LabAgent 从“我部署了本地大模型”讲成“我设计并实现了一套可评测、可扩展、可运维的私有 AI Infra / Agent 平台”。
>
> 当前校准日期：2026-07-10。

## 1. 面试时先讲什么

### 30 秒版本

LabAgent 是一个私有 AI 基础设施项目。我把内网里的本地 GPU 主机通过 SSH 反向隧道接到云服务器，再用 LiteLLM 封装成 OpenAI-compatible API，让 Codex CLI、Cline、Python SDK 等客户端可以像调用 OpenAI 一样调用本地模型。当前已经实现多节点模型路由、RAG Service、Vision 路由、轻量 Agent Router、Codex/Cline 兼容性 smoke test，以及每日全链路巡检脚本。

### 2 分钟版本

这个项目的核心问题是：本地 5090 / 新设备都在 NAT 内网后面，没有公网入口，但团队希望远程使用这些本地大模型做开发。因此我设计了三层架构：

```text
客户端
  -> 云服务器 LiteLLM 网关
  -> SSH Reverse Tunnel
  -> 本地 GPU 节点 LM Studio / RAG / Agent Router
```

云服务器只做轻量控制面，不做推理；5090 承载主代码模型 `qwen-agent`；新设备承载 `embed-local` 和 `vision-local`；RAG Service 运行在 5090，读取本地文档索引；`labagent-agent` 是轻量编排层，把文本、图片和项目知识查询路由到不同 side channel。

我不是只做了部署，还做了：

- OpenAI-compatible API 网关和鉴权。
- 多节点反向隧道路由。
- RAG v1 HTTP 服务。
- Vision smoke benchmark。
- Codex CLI / Cline 团队客户端兼容性验证。
- `scripts/check_labagent_status.ps1` 每日全链路巡检。
- 文档化的故障排查、handoff、benchmark 和路线图。

下一阶段是把 RAG 从 JSON index 升级为 workspace 级向量数据库 + reranker + answer faithfulness eval，让它从 demo 变成工程化知识服务。

## 2. 当前项目的真实边界

已经满足团队基本使用：

- 团队成员可以用 `http://82.156.69.153:8000/v1` + `qwen-agent` 接 Codex / Cline。
- 需要图片能力时可以用 `vision-local`，或者实验性使用 `labagent-agent`。
- 5090 / 新设备 / 云端 LiteLLM 链路有日常检查脚本。

还不是完整生产系统：

- SSH 隧道仍是手动维持，不是 systemd / Windows Service 常驻。
- RAG 仍是本地 JSON index，不是 Qdrant / Chroma。
- RAG 没有多 workspace 隔离。
- RAG 没有 reranker 和引用真实性自动评测。
- `labagent-agent` 是 router / composer，不是真正的 Agent Runtime；它不执行 shell/file 工具，不做 planner loop。
- Claude Code 工具调用仍是实验链路。

面试时要主动讲边界。主动讲边界反而更像工程师。

## 3. 下一阶段为什么优先做 RAG v1.x

不要马上做 mini Codex。原因：

- mini Codex 的范围太大：工具调用、文件 diff、sandbox、回滚、planner、上下文裁剪、trace、权限控制都要做。
- 当前项目已经有 RAG v1 baseline，继续升级能形成清晰闭环。
- RAG v1.x 可以体现工程深度：数据建模、向量数据库、reranker、评测、workspace 隔离、API 设计。
- 团队未来也确实需要“每个人自己的项目文档能被本地模型使用”。

最合理的主线：

```text
RAG v1 JSON index
  -> RAG v1.x workspace + vector db
  -> reranker
  -> citation / faithfulness eval
  -> agentic retrieval
  -> Agent Runtime
```

## 4. RAG v1.x 具体怎么实现

### 4.1 目标能力

把当前“只索引 LabAgent 自己文档”的 RAG，升级为“多 workspace 的项目知识服务”：

```text
workspace: labagent
  docs: README / HANDOFF / docs/*.md

workspace: team_a_project
  docs: team A 的 README / PRD / API / 错误记录

workspace: team_b_project
  docs: team B 的内部文档
```

调用时必须指定 workspace：

```json
{
  "workspace_id": "labagent",
  "query": "当前 qwen-agent 和 vision-local 是什么分工？",
  "top_k": 8
}
```

这样每个团队成员的文档不会混在一起。

### 4.2 数据模型

核心对象：

```text
Workspace
  workspace_id
  name
  root_path
  created_at
  updated_at

Document
  doc_id
  workspace_id
  source_path
  content_hash
  title
  metadata
  updated_at

Chunk
  chunk_id
  workspace_id
  doc_id
  source_path
  chunk_index
  text
  token_count
  embedding
  metadata
```

向量数据库 payload 至少保存：

```json
{
  "workspace_id": "labagent",
  "doc_id": "README.md:sha256",
  "source_path": "README.md",
  "chunk_index": 12,
  "text": "...",
  "title": "当前阶段",
  "content_hash": "..."
}
```

为什么要有 `workspace_id`：

- 检索时可过滤，避免团队 A 的文档污染团队 B。
- 权限模型以后可以围绕 workspace 做。
- benchmark 可以按 workspace 统计。

为什么要有 `content_hash`：

- 文档没变就不重新 embedding，节省时间和流量。
- 后续支持增量索引。

### 4.3 目录结构建议

在现有 `services/rag` 基础上小步演进：

```text
services/rag/
  cli.py                 # 保留 index/search/ask
  server.py              # HTTP API
  index.py               # 当前 JSON index 逻辑
  store_json.py          # JSON baseline store
  store_qdrant.py        # 新增：Qdrant backend
  workspace.py           # 新增：workspace registry / path discovery
  rerank.py              # 新增：reranker adapter
  eval.py                # 新增：faithfulness / citation eval helper
```

不要一上来重写。先定义 store interface：

```python
class VectorStore:
    def upsert_chunks(self, workspace_id: str, chunks: list[Chunk]) -> None: ...
    def search(self, workspace_id: str, query_embedding: list[float], top_k: int) -> list[SearchResult]: ...
    def delete_document(self, workspace_id: str, doc_id: str) -> None: ...
    def health(self) -> dict: ...
```

当前 JSON index 也实现这个接口，Qdrant 也实现这个接口。这样后续可以保留 JSON baseline 做回归。

### 4.4 API 设计

新增 workspace 维度：

```text
GET  /v1/rag/workspaces
POST /v1/rag/workspaces
POST /v1/rag/index
POST /v1/rag/search
POST /v1/rag/ask
GET  /v1/rag/health
```

`POST /v1/rag/search`：

```json
{
  "workspace_id": "labagent",
  "query": "LabAgent 当前多节点路由是什么？",
  "top_k": 20,
  "rerank": true,
  "final_k": 8
}
```

返回：

```json
{
  "workspace_id": "labagent",
  "query": "...",
  "results": [
    {
      "source_id": "S1",
      "source_path": "HANDOFF.md",
      "chunk_index": 3,
      "score": 0.82,
      "rerank_score": 0.91,
      "text": "..."
    }
  ]
}
```

`POST /v1/rag/ask`：

```json
{
  "workspace_id": "labagent",
  "query": "qwen-agent 和 vision-local 分别是什么？",
  "top_k": 20,
  "final_k": 8,
  "rerank": true,
  "require_citations": true
}
```

要求回答中必须引用 `[S1] [S2]`。

### 4.5 Qdrant / Chroma 选型

建议优先 Qdrant：

- API 边界清晰。
- payload filter 适合 workspace_id。
- 工程感更强，面试更好讲。
- 后续可以 Docker / 本机服务化。

Chroma 也可以，但更像本地 notebook / app 内嵌方案。

短期实现建议：

```text
Phase 1: 保留 JSON store，抽象 VectorStore interface
Phase 2: 接 Qdrant local
Phase 3: 双写 JSON + Qdrant 一段时间，结果对比
Phase 4: Qdrant 作为默认，JSON 作为 fallback / baseline
```

### 4.6 Reranker 怎么接

当前 embedding 做的是粗召回：

```text
query -> embedding -> vector search top 20
```

reranker 做精排：

```text
query + candidate chunk -> relevance score
top 20 -> reranker -> top 8
```

接口：

```python
class Reranker:
    def rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]: ...
```

如果模型通过 OpenAI-compatible endpoint 暴露，可以先做 HTTP adapter：

```text
reranker-local -> new device / 8060S
```

没有 reranker 模型时，先用 no-op reranker：

```python
class NoopReranker:
    def rerank(...):
        return candidates[:top_k]
```

这样服务不会因为 reranker 未部署而不可用。

### 4.7 Answer faithfulness / citation eval 怎么做

目标不是证明模型回答“好听”，而是证明它“有证据”。

建议做三个指标：

1. Citation presence
   - 回答中是否包含 `[S1]` 这类引用。

2. Citation validity
   - 引用的 source id 是否存在于本次 retrieved context。

3. Answer support
   - 回答中的关键事实是否能在引用 chunk 中找到。

先不要上复杂 LLM judge。可以从规则开始：

```text
问题：qwen-agent 跑在哪里？
期望关键词：5090, Qwen3-Coder, qwen-agent
必须引用：HANDOFF.md 或 README.md 中对应 chunk
错误关键词：新设备, 8060S, vision-local
```

评测数据：

```text
benchmarks/datasets/rag_faithfulness_cases.jsonl
```

样例：

```json
{
  "id": "route_qwen_agent_node",
  "workspace_id": "labagent",
  "query": "qwen-agent 当前跑在哪台机器上？",
  "required_keywords": ["5090", "qwen-agent"],
  "forbidden_keywords": ["新设备", "8060S"],
  "expected_sources": ["README.md", "HANDOFF.md"]
}
```

通过标准：

```text
citation_presence = true
citation_validity = true
required_keyword_recall >= 0.8
forbidden_keyword_count = 0
```

面试可讲：我没有只看主观答案，而是把 RAG 的“检索正确性、引用真实性、回答忠实性”拆成可自动回归的指标。

## 5. Agent Router 下一步怎么深化

当前 `labagent-agent` 是轻量 router：

```text
文本 -> qwen-agent
图片 -> vision-local -> qwen-agent
项目知识 -> RAG -> qwen-agent
Codex tools 请求 -> 透传 qwen-agent
```

它不是完整 Agent Runtime。

下一步不要直接做大而全的 agent。先做可观测的 router：

### 5.1 加 trace id

每个请求生成：

```text
labagent_trace_id
```

响应里返回：

```json
{
  "labagent": {
    "trace_id": "20260710-...",
    "route": "project_context+image_input",
    "vision_model": "vision-local",
    "rag_top_k": 8,
    "final_model": "qwen-agent"
  }
}
```

日志写到：

```text
logs/agent_traces/*.jsonl
```

面试时能讲：我为 router 加了 traceability，可以定位是 vision、RAG、final model 哪一段出错。

### 5.2 加 intent classifier

当前是 keyword router，后续可以升级为规则 + 小模型分类：

```text
image_input
project_context
coding_request
general_chat
client_tool_passthrough
```

先不要让 LLM 自由决定所有路由，容易不可控。建议：

```text
hard rule first
small classifier second
fallback qwen-agent
```

### 5.3 加错误降级策略

例如：

```text
vision-local 挂了 -> 告诉用户图片服务不可用，但文本仍可回答
RAG 挂了 -> 继续 qwen-agent，但明确说没有检索到项目知识
qwen-agent 挂了 -> 返回明确 502，提示检查 :12340
```

这些都比“静默 hallucination”更工程化。

## 6. 多 workspace RAG 怎么服务团队

你的理解是对的：每个人/每个项目应该有自己的 workspace，而不是把所有文档混到一个向量库。

推荐流程：

```text
团队成员准备文档目录
  -> 注册 workspace
  -> 上传/同步文档
  -> LabAgent index
  -> 查询时指定 workspace_id
```

例如：

```powershell
python -m services.rag.cli workspace create team_a --path F:\TeamA\docs
python -m services.rag.cli index --workspace team_a
python -m services.rag.cli ask --workspace team_a "这个项目怎么启动？"
```

未来 Cline / Codex 侧可以配置：

```text
LABAGENT_WORKSPACE_ID=team_a
```

这样每个成员问的是自己的项目知识。

权限上先简单处理：

```text
API key -> allowed workspaces
```

不要一开始做复杂 RBAC。

## 7. 面试常见问题与回答

### Q1：这个项目和直接在本地开 LM Studio 有什么区别？

直接开 LM Studio 只能本机或局域网用。LabAgent 解决的是 NAT 后本地 GPU 如何变成公网可用的 OpenAI-compatible API，并且支持多节点模型路由、RAG、Vision、客户端兼容性、巡检和评测。

### Q2：为什么用 SSH Reverse Tunnel？

因为 5090 和新设备在内网 NAT 后，没有公网 IP，也不方便做路由器端口映射。SSH 反向隧道由本地机器主动连云服务器，云端监听端口再转发回本地服务。它部署简单、安全边界清楚，也适合低成本云服务器。

### Q3：为什么云服务器只跑 LiteLLM？

云服务器只有 2 核 2GB，不能承载推理、RAG、OpenWebUI 等重服务。设计上把云服务器作为轻量控制面：鉴权、协议统一、模型路由、隧道中转；计算放在本地 GPU 节点。

### Q4：LiteLLM 和 RAG Service 的边界是什么？

LiteLLM 只做模型路由，不读取文档、不切 chunk、不做检索。RAG Service 才负责文档 discovery、chunking、embedding、向量检索、拼 context 和带引用回答。这个边界避免把网关和业务知识服务耦合在一起。

### Q5：为什么 `qwen-agent` 选 Qwen3-Coder-30B？

因为对 coding-agent 客户端来说，最重要的是稳定输出 `message.content`、能完成 patch / file edit / tool workflow。之前测试的一些 reasoning 模型会把预算耗在 `reasoning_content`，final `content` 为空或超时，不适合作为默认执行模型。Qwen3-Coder-30B 在当前 benchmark 和 Codex/Cline smoke 中更稳。

### Q6：`labagent-agent` 是不是一个真正 agent？

现在不是。它是一个轻量 router / composer：根据输入是否有图片、是否命中项目知识、是否是 Codex tool request，把请求路由到 `vision-local`、RAG 或 `qwen-agent`。它不执行 shell/file 工具，也不做 planner loop。真正 Agent Runtime 是后续方向。

### Q7：你怎么证明链路真的可用？

我做了两层验证：

- 端口/隧道层：检查本机 `:1234/:8010/:8020` 和云端 `:8000/:12340/:12341/:18020`。
- API 层：真实调用 `/v1/models`、`qwen-agent` chat、`embed-local` embedding、`vision-local` image、RAG health、`labagent-agent` chat。

现在这些检查被固化到 `scripts/check_labagent_status.ps1`，每天可以跑一次。

### Q8：怎么处理 key 和安全？

真实 key 只放 `.env.local`，不进 Git。文档里统一用 `<LABAGENT_API_KEY>`、`<LABAGENT_RAG_API_KEY>`、`<LABAGENT_AGENT_API_KEY>` 占位。云服务器安全组只放行必要端口。SSH 使用密钥认证。

### Q9：为什么 RAG 要做 workspace？

团队成员的项目文档不同，如果混在同一个索引里，会出现知识污染和权限问题。workspace_id 可以把文档、索引、检索和权限隔离。每个问题只在指定 workspace 内检索，结果更可控。

### Q10：为什么要 reranker？

embedding 向量召回适合快速找相似内容，但对列表、配置、短事实和多跳问题会有召回偏差。reranker 可以对 top 20 候选重新按 query relevance 排序，提高最终 top 8 context 的质量。

### Q11：怎么评价 RAG 回答有没有胡说？

我会拆成三个层次：

- 检索是否命中正确 source。
- 回答是否带真实引用。
- 回答中的关键事实是否能被引用 chunk 支持。

先用规则型 eval 起步，再考虑 LLM judge。

### Q12：这个项目最大的工程难点是什么？

不是单个模型调用，而是端到端稳定性：

- NAT 网络和反向隧道容易断。
- OpenAI-compatible chat 能通，不代表 Codex / Cline 工具流能通。
- RAG 检索看似能答，但可能引用不真实。
- Vision 能看图，不代表代码截图 OCR 足够准。
- 多节点模型路由必须有健康检查和降级。

### Q13：如果某天 David 连不上，你怎么排查？

按层排查：

1. `scripts/check_labagent_status.ps1`
2. 看云端 `:12340/:12341/:18020` 是否监听。
3. 看 `qwen-agent` 是否能返回 `pong`。
4. 看 `labagent-agent /health` 是否可达。
5. 如果 health 通但 chat 502，检查 Agent Router 是否用脚本启动并加载了正确 `LABAGENT_BASE_URL`。

### Q14：Vision 为什么不一定要 30B？

当前 Vision 在平台里主要做“眼睛”：OCR、截图理解、UI 文本提取。最终推理和代码修改仍交给 `qwen-agent`。因此可以考虑默认用更轻的 VL 模型，复杂 GUI / 多图 / computer use 再切到更强 Vision。最终要靠 LabAgent 自己的 VL benchmark 决定。

### Q15：这个项目怎么写进简历？

可以写成：

```text
LabAgent Platform: 设计并实现一套私有 AI Infra 平台，将 NAT 内网中的本地多 GPU 大模型通过 SSH Reverse Tunnel 和 LiteLLM 暴露为 OpenAI-compatible API，支持 Codex CLI / Cline 等客户端远程调用。实现多节点模型路由、RAG Service、Vision side-channel、轻量 Agent Router、客户端兼容性 smoke test 和全链路巡检脚本；基于 benchmark 对模型选型、RAG 检索质量和工具调用兼容性进行持续评估。
```

更偏工程的 bullet：

```text
- Built an OpenAI-compatible private LLM gateway over SSH reverse tunnels, routing cloud API requests to local RTX 5090 / multi-GPU inference nodes.
- Implemented a lightweight Agent Router combining coding model, vision model, and RAG side-channel with route metadata and fallback behavior.
- Built a RAG Service baseline with markdown chunking, embedding-based retrieval, cited answers, HTTP APIs, and planned migration to workspace-isolated vector DB + reranker.
- Designed smoke/eval scripts for Codex CLI compatibility, vision routing, embedding health, and full-link operational status checks.
```

## 8. 你应该按什么顺序学习代码

第一层：先懂链路。

- `docs/SETUP.md`
- `docs/NETWORK.md`
- `scripts/start_5090_services.ps1`
- `scripts/check_labagent_status.ps1`

第二层：再懂 RAG。

- `docs/RAG_LEARNING_NOTES.md`
- `services/rag/README.md`
- `services/rag/cli.py`
- `services/rag/server.py`
- `services/rag/index.py` 或当前负责 index/search 的模块

第三层：再懂 Agent Router。

- `docs/AGENT_ROUTER_LEARNING_NOTES.md`
- `services/agent/router.py`
- `services/agent/server.py`

第四层：懂团队客户端兼容。

- `docs/CODEX_CLI_COMPATIBILITY.md`
- `docs/TEAM_CLIENT_COMPATIBILITY.md`
- `benchmarks/fixtures/codex_cli_smoke/TASKS.md`

第五层：懂评测和简历故事。

- `docs/BENCHMARK_DESIGN.md`
- `docs/BENCHMARK_RESULTS.md`
- `docs/Progress_Summary.md`
- 本文档

## 9. 下一步具体任务拆解

### Task A：RAG store interface

目标：让 JSON store 和未来 Qdrant store 共用接口。

要改：

- `services/rag/store_json.py`
- `services/rag/types.py`
- `services/rag/cli.py`
- `services/rag/server.py`

验收：

- 原有 `index/search/ask` 行为不变。
- 单元测试覆盖 JSON store。
- `check_labagent_status.ps1` 仍通过核心链路。

### Task B：workspace registry

目标：支持多 workspace。

要改：

- 新增 `services/rag/workspace.py`
- 新增 `data/rag/workspaces.json`，本地忽略不进 Git。
- CLI 增加 `workspace list/create/remove`。
- HTTP API 增加 `/v1/rag/workspaces`。

验收：

- `labagent` workspace 可索引当前仓库。
- 第二个测试 workspace 不污染 `labagent` 检索结果。

### Task C：Qdrant backend

目标：把向量检索从 JSON index 升级到 Qdrant。

要改：

- 新增 `services/rag/store_qdrant.py`
- 增加环境变量 `LABAGENT_RAG_STORE=qdrant`
- 增加 `LABAGENT_QDRANT_URL`

验收：

- JSON 和 Qdrant 对同一批 query 的 top-k 结果可对比。
- Qdrant 支持按 `workspace_id` filter。

### Task D：reranker

目标：top 20 召回后重排到 top 8。

要改：

- 新增 `services/rag/rerank.py`
- `search` API 增加 `rerank` 和 `final_k`

验收：

- 没有 reranker 时服务不挂，走 no-op。
- 有 reranker 时结果包含 `rerank_score`。

### Task E：faithfulness eval

目标：自动检查回答是否有引用、引用是否存在、事实是否被支持。

要改：

- 新增 `benchmarks/rag_faithfulness_eval.py`
- 新增 `benchmarks/datasets/rag_faithfulness_cases.jsonl`

验收：

- 至少 10 个 LabAgent 项目事实问题。
- 输出 JSONL 和 summary。
- 能抓出节点路由说错、引用缺失、引用不存在等问题。

### Task F：router trace

目标：让 `labagent-agent` 每次请求可追踪。

要改：

- `services/agent/router.py`
- `services/agent/server.py`

验收：

- 响应里有 `labagent.trace_id`。
- route、final_model、vision_model、rag_used 等进入 trace JSONL。

## 10. 下一步推荐执行顺序

最推荐：

```text
1. RAG store interface
2. workspace registry
3. Qdrant backend
4. reranker
5. faithfulness eval
6. router trace
```

不要同时开太多线。每一步都要：

```text
实现 -> 单元测试/脚本验证 -> 文档同步 -> Git commit -> 运行 check_labagent_status.ps1
```

## 11. 你现在应该能讲清楚的核心句子

如果面试官问“你这个项目的技术含量在哪里”，回答可以是：

```text
我没有只停留在部署模型，而是把本地多 GPU 推理节点、云端轻量网关、OpenAI-compatible 协议、多客户端兼容、RAG 检索服务、Vision side-channel、Agent Router 和全链路运维检查串成了一个可验证系统。后续我正在把 RAG 从 JSON baseline 升级到 workspace-isolated vector DB + reranker + citation eval，这样可以证明回答不仅能生成，而且能被项目文档证据支持。
```

## 12. 对照 Agent 面经怎么回答

这组题更偏“完整 Coding Agent Runtime”。LabAgent 当前不是完整 Coding Agent，而是私有 AI Infra + 模型网关 + RAG Service + 轻量 router。回答时不要硬说已经实现工具执行、上下文压缩、长期记忆和 patch 回滚；要把已完成能力、当前边界、下一步设计讲清楚。

### 1. 先整体介绍本地 Coding Agent 项目，从输入任务到最终修改代码，完整链路怎样？

LabAgent 当前的完整链路分两类。

团队主链路：

```text
用户在 Codex / Cline 输入任务
  -> OpenAI-compatible 请求
  -> 云端 LiteLLM :8000
  -> SSH :12340
  -> 5090 LM Studio qwen-agent
  -> 客户端执行文件读写 / shell / diff
```

这里真正执行文件修改的是 Codex / Cline 客户端，不是 LabAgent 服务器。LabAgent 负责把本地模型稳定暴露成公网 API，并验证客户端 workflow。

实验统一入口：

```text
用户请求 labagent-agent
  -> 云端 :18020
  -> 5090 Agent Router :8020
  -> 根据输入路由：
       普通文本 -> qwen-agent
       图片 -> vision-local -> qwen-agent
       项目知识 -> RAG Service -> qwen-agent
       Codex tools Responses 请求 -> 透传 qwen-agent
```

当前边界：LabAgent Router 不执行文件修改，不是完整 Coding Agent Runtime。

为了更硬地回答这题，下一步要做 `router trace`，把一次请求的 route、side channel、最终模型和耗时记录下来。

### 2. Agent 支持不同模型后端吗？多个模型服务如何抽象请求格式、响应结构、错误码和重试？

当前支持。模型后端通过 LiteLLM 做 OpenAI-compatible 统一：

```text
qwen-agent   -> 5090 :12340
embed-local  -> 新设备 :12341
vision-local -> 新设备 :12341
labagent-agent -> 5090 :8020 / 云端 :18020
```

抽象方式：

- 外部统一 OpenAI-compatible API。
- `model` 字段决定路由。
- LiteLLM 负责 chat / embeddings 的基础协议适配。
- Agent Router 在 `services/agent/router.py` 内把 route metadata 放进 `labagent` 字段。

当前不足：

- 错误码还比较粗，很多后端失败体现为 500 / 502。
- retry 还没有系统化。
- 没有统一 `error_code` 枚举。

后续设计：

```text
UPSTREAM_UNAVAILABLE
MODEL_NOT_LOADED
TUNNEL_DOWN
RAG_UNAVAILABLE
VISION_UNAVAILABLE
AUTH_FAILED
TIMEOUT
```

并在 router / RAG response 中统一返回：

```json
{
  "ok": false,
  "error_code": "TUNNEL_DOWN",
  "message": "...",
  "retryable": true,
  "hint": "Start .\\scripts\\start_5090_services.ps1 -Action qwen-tunnel"
}
```

### 3. 工具系统怎么做？新工具从定义、注册、被发现到调用的流程是什么？

当前 LabAgent 自己还没有工具系统。工具执行主要由 Codex / Cline 客户端完成。LabAgent 做过的工作是：

- 验证 Codex CLI 通过 `qwen-agent` 能触发 PowerShell / 文件工具。
- 修复 `labagent-agent` 对 Codex Responses `tools` 字段的吞掉问题。
- 对无图片的 Codex tools 请求直接透传到上游 `qwen-agent`，保留客户端工具调用协议。

所以面试时应这样答：

```text
当前项目没有自研工具 registry；我刻意把工具执行放在 Codex/Cline 客户端侧，LabAgent 先解决后端模型接入、协议透传和多节点路由。下一阶段如果做 Agent Runtime，我会实现 tool registry。
```

未来工具系统设计：

```text
ToolSpec
  name
  description
  input_schema
  output_schema
  timeout
  permission_level

ToolRegistry
  register(tool)
  list_tools(intent)
  execute(tool_name, args)
```

调用链：

```text
Planner 选择工具
  -> ToolRegistry 校验 schema
  -> Permission / sandbox 检查
  -> 执行工具
  -> 结构化 Observation
  -> 回到模型继续推理
```

### 4. 工具调用失败时怎么恢复和重试？

当前 LabAgent 的工具调用失败恢复主要依赖 Codex / Cline 客户端。项目里已经验证过 Codex C1-C6 中出现过：

- PowerShell 不支持 `&&`。
- 未安装 `pytest`。
- 直接跑 `python tests/test_app.py` 有 import path 问题。

Codex 能回退到 `python -m unittest` 完成验证。

LabAgent 自己已做的恢复：

- Vision side channel 失败时不直接让整个请求崩溃，而是记录 error 交给最终模型。
- RAG 分支失败时可把失败原因反馈给最终回答上下文。
- 每日巡检脚本会给出具体恢复命令。

后续要补：

- router 级 retry。
- typed error code。
- tool failure observation。
- timeout 后降级路径。

### 5. 多轮任务中的上下文治理，有真实场景吗？

当前 LabAgent 还没有完整多轮上下文治理模块。已有相关基础：

- RAG Service 把项目文档切 chunk，避免把所有文档塞进 prompt。
- Codex CLI C1-C6 验证了小型多步开发 workflow。
- `HANDOFF.md` / `Progress_Summary.md` / `PROJECT_DEEP_DIVE...` 起到人工 handoff memory 的作用。

可以这样回答：

```text
当前我没有把上下文治理做成 Agent Runtime 内部模块，但已经在项目文档、RAG chunking 和 handoff 流程上做了工程化准备。下一步会把 workspace RAG、文件摘要和 trace 结合起来，形成可自动检索的上下文层。
```

### 6. 上下文压缩后怎么判断没有破坏当前任务？

当前还没有自动上下文压缩。未来标准：

- 必须保留 task goal。
- 必须保留已改文件列表。
- 必须保留失败测试 / 错误日志。
- 必须保留用户显式约束。
- 压缩后要跑 retrieval / summary consistency check。

评测方式：

```text
原始上下文 -> 压缩摘要 -> 用摘要继续完成任务
对比：
  是否仍能找到关键文件
  是否仍能通过测试
  是否违反用户约束
```

### 7. 任务摘要、文件摘要、过程笔记怎么生成和维护？

当前是人工文档化：

- `HANDOFF.md`：当前事实和下一步。
- `Progress_Summary.md`：阶段性成果。
- `CHANGELOG.md`：变更历史。
- `PROJECT_DEEP_DIVE...`：面试和深挖。

未来自动化设计：

```text
TaskTrace
  goal
  files_read
  files_modified
  commands_run
  tests_run
  errors_seen
  decisions
```

每次任务结束生成 summary，并写入 workspace memory。摘要必须带 source links，避免无来源记忆污染。

### 8. 摘要遗漏关键约束导致 Agent 做错，怎么发现并修正？

未来检测：

- 对照用户原始要求做 constraint checklist。
- 每次执行前让 agent 输出“当前约束列表”。
- 测试失败或 review 发现偏差时，把缺失约束写回 task trace。

在 LabAgent 项目里对应：

- 每次收尾要求更新 handoff。
- 代码变更后跑 check script / benchmark。
- 文档里明确记录失败原因和恢复命令。

### 9. 长期记忆保存过时文件摘要，污染怎么处理？

未来方案：

- 文件摘要绑定 `content_hash`。
- 文件变更后旧摘要自动失效。
- RAG chunk payload 保存 `content_hash` 和 `updated_at`。
- 检索时过滤过期摘要。

这正是 RAG v1.x 要引入 Document / Chunk / content_hash 数据模型的原因。

### 10. 模型把错误结论写进记忆，后续一直沿用，怎么纠错？

原则：记忆不能只有模型结论，必须有证据来源。

未来方案：

- 记忆分两类：事实型 memory 和假设型 note。
- 事实型 memory 必须绑定 source。
- 如果新证据冲突，标记旧 memory deprecated。
- 重要事实用 eval case 固化。

对应 LabAgent：

- 节点路由事实如 `qwen-agent -> 5090` 必须来自 README / HANDOFF。
- answer faithfulness eval 要抓“把节点映射说错”的错误。

### 11. 多轮执行中重复读同一文件或重复调用工具，怎么识别重复状态？

当前没有 Agent Runtime 内置去重。未来在 trace 层做：

```text
file_read_cache[path, content_hash]
tool_call_cache[tool_name, args_hash, workspace_state_hash]
```

如果文件 content_hash 没变，重复读取可以复用摘要。

如果工具参数一样、工作区状态没变，重复执行要提示 planner：这一步已经做过。

### 12. 你怎么看 RAG、Memory 和 Context Engineering？

可以这样答：

- RAG：从外部知识库按需取证据，解决“模型不知道项目事实”的问题。
- Memory：跨任务保存稳定偏好、历史决策和长期事实，解决“多次会话连续性”的问题。
- Context Engineering：决定当前这一次请求放什么上下文、怎么裁剪、怎么压缩、怎么排序，解决“上下文窗口有限且噪声会伤害模型”的问题。

在 LabAgent 中：

```text
RAG = services/rag，查项目文档和证据
Memory = 目前主要是 HANDOFF / Progress / CHANGELOG，未来进入 workspace memory
Context Engineering = router 决定是否加入 RAG、vision summary、side-channel 输出
```

### 13. Agent Harness 怎么理解？和单纯调用 LLM API 的区别？

单纯 LLM API：

```text
prompt -> model -> answer
```

Agent Harness：

```text
task
  -> context builder
  -> model call
  -> tool call
  -> observation
  -> retry / validation
  -> final answer / patch
  -> trace / eval
```

LabAgent 当前已经有 harness 的一部分：

- router
- RAG side channel
- vision side channel
- Codex/Cline 客户端兼容测试
- benchmark scripts
- full-link status check

但还没有完整 planner/tool loop。

### 14. Agent 有没有评测体系？怎么设计 benchmark、case、指标？

有基础评测体系：

- model latency
- gateway health
- agent tasks
- RAG oracle
- RAG retrieval
- repo map
- patch task
- Cline dialogue
- embedding health
- vision local eval
- Codex CLI smoke C1-C6
- full-link status check

指标：

- `content` 非空率。
- finish_reason。
- latency。
- strict pass / soft pass。
- keyword recall。
- patch 是否可用。
- API 是否返回正确结构。
- RAG 是否命中正确 source。

下一步要补：

- faithfulness eval。
- tool-call eval。
- trace eval。
- failure-mode eval。

### 15. 错误 patch 怎么回滚、验证和再尝试？

当前 LabAgent 自己不执行 patch；Codex/Cline 客户端负责文件编辑。已有验证是 Codex C6：故意破坏实现后，根据失败测试修复。

未来如果自研 Agent Runtime：

```text
1. patch 前记录 git diff
2. apply patch
3. run tests / lint
4. 失败则保留错误 observation
5. revert patch or apply corrective patch
6. 最多重试 N 次
7. 输出 trace
```

关键是所有 patch 必须可回滚，不能直接覆盖用户改动。

### 16. 平时用什么 AI？一个需求怎么用 AI 辅助开发？

可以结合真实流程回答：

```text
我会先用 AI 帮我拆需求和识别风险，但不会直接让它大改。然后我让它读项目文档和相关代码，给出最小实现方案。实现后必须跑脚本/测试/全链路检查，并把变更同步到 HANDOFF、CHANGELOG 和专题文档。
```

这和当前 LabAgent 的工作流一致。

### 17. 怎么拆需求、读代码、让模型改代码、跑测试和 review？

推荐回答：

```text
1. 先明确目标和验收标准。
2. 用 rg / 文件阅读定位相关模块。
3. 小步修改，不做无关重构。
4. 跑最小相关测试或 smoke。
5. 看 git diff，确认没有泄露 key 或改错文档。
6. 更新 handoff / changelog。
7. commit + push。
```

对应 LabAgent：

- 部署变更跑 `check_labagent_status.ps1`。
- RAG 变更跑 index/search/ask。
- Router 变更跑 health/chat/responses smoke。
- 客户端兼容变更跑 Codex fixture。

## 13. 这份面经暴露出的项目差距

和完整 Coding Agent Runtime 相比，LabAgent 当前缺这些：

```text
1. Tool registry
2. Planner loop
3. Patch apply / rollback
4. Context compression
5. Long-term memory with invalidation
6. Trace viewer
7. Tool failure recovery policy
8. Agent harness benchmark
```

但这不是坏事。它说明下一阶段项目深挖路线很清楚：

```text
先补 RAG v1.x / eval / trace
再补 tool registry / planner / patch rollback
最后形成 mini Agent Runtime
```

面试时不要把“未来规划”说成“已经完成”。正确表达是：

```text
我当前已经把模型网关、多节点路由、RAG baseline、Vision side channel、客户端兼容和巡检做成了可用系统。完整 Coding Agent Runtime 还在路线图中，我计划先从 trace、tool registry 和 patch rollback 三个最小闭环开始做。
```
