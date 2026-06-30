# RAG 学习与实现笔记

> 目标：边做边学，把 LabAgent 的 RAG 从概念、代码、调试、评测到后续升级路线都记录清楚。

## 1. RAG 到底是什么

RAG 全称是 Retrieval-Augmented Generation，中文通常叫“检索增强生成”。

你可以把它理解成一个会查资料的问答流程：

```text
普通聊天：
你问问题 -> 大模型靠记忆回答

RAG：
你问问题 -> 系统先查资料 -> 把查到的片段交给大模型 -> 大模型基于资料回答
```

为什么需要 RAG？

大模型本身不知道你的私有项目文档、当前服务器配置、历史模型 benchmark 结果和刚刚发生的决策。把这些东西每次都复制进 prompt 里，太长、太慢、太贵，而且很容易超出上下文长度。RAG 的作用就是先从资料库里“挑出最相关的几段”，再把这几段塞给模型。

所以 RAG 不是微调，也不是让模型永久记住你的文档。它更像“考试时允许开卷，但先由系统帮你把最相关的几页翻出来”。

## 2. 一个最小 RAG 流程

LabAgent 当前的流程是：

```text
1. 准备资料
   README.md / HANDOFF.md / docs/*.md

2. 切成片段
   长文档太大，所以按标题和长度切成 chunk

3. 生成向量
   用 embed-local 把每个 chunk 变成一串数字

4. 保存索引
   在 data/rag/index.json 里保存 chunk 文本 + 向量 + 来源

5. 用户提问
   例如：“LabAgent 当前多节点路由是什么状态？”

6. 问题也生成向量
   用同一个 embed-local 把问题变成数字

7. 检索
   比较“问题向量”和“chunk 向量”的相似度，找 top-k 片段

8. 生成答案
   把 top-k 片段作为 [S1] [S2] 证据交给 qwen-agent，让它带引用回答
```

一句话版：

```text
RAG = 先找资料，再让模型根据资料回答。
```

## 3. 这里要区分三个角色

| 角色 | 它做什么 | 它不做什么 |
|------|----------|------------|
| LiteLLM | 根据 `model` 名字把请求转发到 5090 或新设备 | 不读文档，不切 chunk，不保存索引 |
| Embedding 模型 | 把文档片段或用户问题变成向量 | 不理解项目架构，也不生成最终答案 |
| RAG Service | 读取 5090 本地文档索引，调用 embedding 检索，再调用 chat 模型回答 | 不替代 LiteLLM，也不是新的大模型 |

所以当前架构里，新设备上的 embedding 模型是合理的。RAG Service 可以跑在 5090，上面有项目文档和索引；它通过云服务器 LiteLLM 的 `embed-local` 路由调用新设备上的 embedding，再通过 `qwen-agent` 路由调用 5090 本机 LM Studio 生成答案。

## 4. 核心概念

| 概念 | 白话解释 | 本项目当前对应 |
|------|----------|----------------|
| Corpus | 知识库原始资料 | `README.md`、`HANDOFF.md`、`docs/*.md` |
| Chunk | 从长文档切出来的小片段 | `services/rag/chunking.py` |
| Embedding | 把文字变成数字向量 | `embed-local`，Nomic Embed Text v1.5，768 维 |
| Vector Index | 存 chunk 和向量的地方 | `data/rag/index.json` |
| Retrieval | 按问题找相似 chunk | cosine similarity + keyword/entity boost |
| Context | 检索出来塞给模型的证据 | `[S1]`、`[S2]` source blocks |
| Generation | 模型基于 context 生成答案 | `qwen-agent` / Qwen3-Coder-30B |
| Citation | 答案里标注证据来自哪里 | `[S1]`、`[S2]` |
| Reranker | 对初筛结果再排一次序的模型 | 还没接入，后续放新设备 |

## 5. 当前代码结构

```text
services/rag/
├── cli.py          # 命令行入口：index / search / ask
├── server.py       # RAG Service v1 HTTP API
├── chunking.py     # Markdown 发现和切块
├── client.py       # OpenAI-compatible HTTP client
├── index_store.py  # JSON index、cosine similarity、retrieve
├── pipeline.py     # search + answer pipeline
└── README.md       # 使用说明
```

评测位置：

```text
benchmarks/rag_retrieval_eval.py
```

运行数据：

```text
data/rag/index.json
```

`data/rag/` 是本地运行数据，不进 Git。

默认 discovery 会跳过原始 review 和外部系统提示词文件：

```text
docs/CODE_REVIEW_ISSUES.md
docs/claude-fable-5.md
docs/LabAgent_Platform_V*.md
```

原因很简单：它们不是 LabAgent 自己的事实源，进索引会污染 RAG 回答。外部 AI 给出的建议可以人工阅读和分流，但不能直接进入默认项目事实库。

## 6. 当前实现阶段

### RAG v0：命令行闭环

已经完成：

```text
文档加载
Markdown chunking
embedding
本地 JSON 向量索引
相似度检索
带引用回答
retrieval benchmark
```

### RAG Service v1：HTTP 服务

新增：

```text
GET  /health
GET  /v1/models
GET  /v1/rag/sources
POST /v1/rag/search
POST /v1/rag/ask
POST /v1/chat/completions
```

这版 v1 还不是“最终生产 RAG”。它的目标是让 David / Cline / OpenWebUI / 脚本可以远程调试 5090 上的 RAG，而不是只在 5090 命令行里跑。

## 7. 如何在 5090 本机调试 RAG

前提：

```text
1. 5090 的 qwen-agent 隧道可用（:12340）
2. 新设备的 embed-local 隧道可用（:12341）
3. 云服务器 LiteLLM 正常
4. 当前仓库在 5090 的 E:\qwen_setup
```

如果 5090 本机只 load 了 Qwen-Coder，没有 load embedding 模型，这是正常状态。只要新设备的 embedding 模型和 `:12341` 隧道可用，5090 上的 RAG 仍然可以通过 LiteLLM 调用 `embed-local`。

### 第一步：设置环境变量

PowerShell：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"
```

这就是“统一 LiteLLM 网关模式”：embedding 和 chat 都走云上的 LiteLLM，再由它分别转发到新设备和 5090。

也可以显式拆成两个 endpoint：

```powershell
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen/qwen3-coder-30b"
```

这个模式的意思是：问题 embedding 走云上的 LiteLLM，到新设备；最终回答直接调用 5090 本机 LM Studio。它适合“5090 只 load Qwen-Coder，新设备 load embedding”的状态。

### 第二步：重建索引

```powershell
python -m services.rag.cli index
```

你应该看到类似：

```text
Indexed 354 chunks from 21 files into data/rag/index.json using embed-local.
```

如果这里失败，常见原因是：

```text
embed-local 隧道没开
新设备 LM Studio 没 load embedding 模型
LABAGENT_API_KEY 没设置，公网 LiteLLM 不通
```

### 第三步：先看检索，不让大模型直接回答

```powershell
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？" --top-k 5
```

这一步只做 retrieval。它回答的是“系统觉得哪些文档片段最相关”。

如果 search 找不到正确文档，说明问题在检索层，不是 Qwen 回答能力的问题。

如果这里报 `ConnectionRefusedError` 或 `URLError`，先看错误里的 endpoint。比如：

```text
http://127.0.0.1:8000/v1/embeddings
```

这通常说明你没有设置 `LABAGENT_BASE_URL` 或 `LABAGENT_EMBED_BASE_URL`，于是 CLI 去请求本机默认 8000 端口，但 5090 上没有 LiteLLM 服务。

### 第四步：完整问答

```powershell
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

这一步是：

```text
问题 -> embedding -> 检索 top-k -> 拼 context -> qwen-agent 生成答案
```

回答里应该出现 `[S1]`、`[S2]` 这类引用。

## 8. 如何启动 RAG Service v1

在 5090 项目目录执行：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"

python -m services.rag.server --host 127.0.0.1 --port 8010
```

如果要显式拆开 embedding/chat endpoint：

```powershell
$env:LABAGENT_EMBED_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_CHAT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen/qwen3-coder-30b"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"

python -m services.rag.server --host 127.0.0.1 --port 8010
```

本地验证：

```powershell
curl.exe http://127.0.0.1:8010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

搜索：

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/search `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"query":"LabAgent 当前有哪些公网模型路由？","top_k":5}'
```

问答：

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/ask `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"query":"LabAgent 当前多节点路由是什么状态？","top_k":8}'
```

OpenAI-compatible 兼容入口：

```powershell
curl.exe http://127.0.0.1:8010/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"model":"labagent-rag","messages":[{"role":"user","content":"LabAgent 当前多节点路由是什么状态？"}],"max_tokens":900}'
```

## 9. David / Cline 远程能不能用 RAG

可以，但要分清“文档在哪里”。

RAG 的文档不需要在 David 机器上。RAG index 在 5090 的 `data/rag/index.json`，RAG Service 也跑在 5090。David / Cline 只是通过 HTTP 调 5090 上的 RAG Service。

也就是说：

```text
David / Cline -> HTTP -> 5090 RAG Service -> 本地索引 -> embedding -> chat
```

## 10. 路由与侧通道

当前 `labagent-agent` 只是一个 router，不是完整 Agent Runtime。

它的职责是：

- 判断是否需要视觉 side channel。
- 判断是否需要 RAG side channel。
- 把 side channel 结果交给 `qwen-agent` 收口。

它的下一步，不是直接做“更大的模型”，而是先把 side channel 失败恢复、streaming、图像回放和更聪明的路由做好。

## 11. 质量问题

当前已经看到两个质量问题：

1. 检索召回有偏差。比如“有哪些公网模型路由？”这类问题，最应该命中的 README 表格有时没进 top-k。
2. 回答可能不完整，但不 hallucinate。比如 8060S 状态、`qwen-think` baseline、云入口等内容，有时因为没被召回就不会出现在答案里。

这说明问题在 retrieval coverage，不是模型“胡说八道”。

## 12. 下一步

RAG v1.x 方向：

1. 用 Qdrant 或 Chroma 替换 JSON index。
2. 在新设备上接入 reranker。
3. 做 answer faithfulness / citation eval。
4. 把 `vision-local` 的最小 smoke 固化为正式 VL benchmark。
5. 继续补 `tool_call_eval`、`patch_apply_eval`、`repo_task_eval`、`trace_eval`。

## 13. 你可以把它当成什么

最实用的理解是：

- RAG 负责“找资料”。
- `qwen-agent` 负责“写最终答案”。
- `vision-local` 负责“看图”。
- `labagent-agent` 负责把这些串起来。

这不是一个单模型，而是一个分工明确的系统。
