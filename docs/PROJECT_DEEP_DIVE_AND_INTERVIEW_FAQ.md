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

