# RAG 学习与实现笔记

> 目标：边做边学，把 LabAgent 的 RAG 从概念、代码、调试、评测到后续升级路径都记录清楚。

## 1. RAG 到底在干嘛

RAG 全称是 Retrieval-Augmented Generation，中文通常叫“检索增强生成”。

你可以把它理解成一个会查资料的问答流程：

```text
普通聊天：
你问问题 -> 大模型凭记忆回答

RAG：
你问问题 -> 系统先查你的资料 -> 把查到的片段交给大模型 -> 大模型基于资料回答
```

为什么需要 RAG？

大模型本身不知道你的私有项目文档、当前服务器配置、历史模型评测结果和刚刚发生的决策。把这些信息全部复制进每次 prompt 又很长、很慢、很贵，而且容易超过上下文长度。RAG 的作用就是先从资料库里“挑出最相关的几段”，只把这几段塞给模型。

所以 RAG 不是微调，也不是让模型永久学会你的文档。它更像“考试时允许开卷，但先由系统帮你把最相关的几页翻出来”。

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
   data/rag/index.json 里保存 chunk 文本 + 向量 + 来源

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

## 3. 核心概念

| 概念 | 白话解释 | 本项目当前对应 |
|------|----------|----------------|
| Corpus | 知识库原始资料 | `README.md`、`HANDOFF.md`、`docs/*.md` |
| Chunk | 从长文档切出来的小片段 | `services/rag/chunking.py` |
| Embedding | 把文字变成数字向量 | `embed-local`，Nomic Embed Text v1.5，768 维 |
| Vector Index | 存 chunk 和向量的地方 | `data/rag/index.json` |
| Retrieval | 按问题找相似 chunk | cosine similarity + keyword/entity boost |
| Context | 检索出来塞给模型的证据 | `[S1]`、`[S2]` source blocks |
| Generation | 模型基于 context 生成答案 | `qwen-agent` / Qwen3-Coder-30B |
| Citation | 答案里标注来自哪个证据 | `[S1]`、`[S2]` |
| Reranker | 对初筛结果再排序的模型 | 未接入，后续放新设备 |

## 4. 当前代码结构

```text
services/rag/
├── cli.py          # 命令行入口：index / search / ask
├── server.py       # RAG Service v1 HTTP API
├── chunking.py     # Markdown 发现与切块
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

默认 discovery 会跳过 raw review 和外部系统提示词文件：

```text
docs/CODE_REVIEW_ISSUES.md
docs/claude-fable-5.md
```

原因：它们不是 LabAgent 项目事实本身，进入索引会污染 RAG 回答。

## 5. 当前实现阶段

### RAG v0：命令行闭环

已完成：

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

这个 v1 还不是“最终生产 RAG”。它的目标是让 RAG 可以被 David/Cline/OpenWebUI/脚本远程调试，而不是只能在 5090 命令行里跑。

## 6. 如何在 5090 本机调试 RAG

前提：

```text
1. 5090 的 qwen-agent 隧道可用（:12340）
2. 新设备的 embed-local 隧道可用（:12341）
3. 云服务器 LiteLLM 正常
4. 当前仓库在 5090 的 E:\qwen_setup
```

### 第一步：设置环境变量

PowerShell：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"
```

### 第二步：重建索引

```powershell
python -m services.rag.cli index
```

你应该看到类似：

```text
Indexed 333 chunks from 21 files into data/rag/index.json using embed-local.
```

如果这里失败，通常是：

```text
embed-local 隧道没开
新设备 LM Studio 没 load embedding 模型
LABAGENT_API_KEY 没设置
公网 LiteLLM 不通
```

### 第三步：只看检索，不让大模型回答

```powershell
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？" --top-k 5
```

这一步只做 retrieval。它回答的是：“系统觉得哪些文档片段最相关？”

如果 search 找不到正确文档，说明问题在检索层，不是 Qwen 回答能力的问题。

### 第四步：完整问答

```powershell
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

这一步会：

```text
问题 -> embedding -> 检索 top-k -> 拼 context -> qwen-agent 生成答案
```

回答里应该出现 `[S1]`、`[S2]` 这种引用。

## 7. 如何启动 RAG Service v1

在 5090 项目目录执行：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"
$env:LABAGENT_RAG_API_KEY = "<LABAGENT_RAG_API_KEY>"

python -m services.rag.server --host 127.0.0.1 --port 8010
```

本机调试：

```powershell
curl.exe http://127.0.0.1:8010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

搜索：

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/search `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前有哪些公网模型路由？\",\"top_k\":5}'
```

问答：

```powershell
curl.exe http://127.0.0.1:8010/v1/rag/ask `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"LabAgent 当前多节点路由是什么状态？\",\"top_k\":8}'
```

OpenAI-compatible 兼容入口：

```powershell
curl.exe http://127.0.0.1:8010/v1/chat/completions `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>" `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"labagent-rag\",\"messages\":[{\"role\":\"user\",\"content\":\"LabAgent 当前多节点路由是什么状态？\"}],\"max_tokens\":900}'
```

## 8. David / Cline 远程能不能用 RAG

可以，但要分清楚“文档在哪里”。

RAG 的文档不需要在 David 主机上。RAG index 在 5090 的 `data/rag/index.json`，RAG Service 也跑在 5090。David/Cline 只是通过 HTTP 问 5090 的 RAG Service。

也就是说：

```text
David/Cline
  -> HTTP 请求
  -> 云服务器或 SSH 隧道
  -> 5090 RAG Service
  -> 5090 本地 data/rag/index.json
  -> embed-local / qwen-agent
  -> 带引用答案返回 David
```

David 不需要有这些 docs 文件。它只需要能访问 RAG Service 的 URL。

当前最简单的远程方式是再开一个 SSH 反向隧道，把 5090 的 RAG Service 暴露到云服务器本地端口：

```powershell
ssh -N -R 18010:127.0.0.1:8010 -i C:\Users\N\.ssh\id_ed25519 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=10 ubuntu@82.156.69.153
```

然后 David 测试：

```powershell
curl.exe http://82.156.69.153:18010/health `
  -H "Authorization: Bearer <LABAGENT_RAG_API_KEY>"
```

如果安全组没有开放 `18010`，David 访问不到。这时有两个选择：

```text
1. 临时开放云服务器 TCP 18010，只给自己测试用
2. 后续用 Nginx/Caddy 把 /rag 反代到 127.0.0.1:18010，并加鉴权/HTTPS
```

云服务器 2GB 内存很小，所以不要把 RAG Service 部署在云服务器上。云服务器只做转发入口。

## 9. Cline 里怎么提问

如果 Cline 直接配置到普通 `qwen-agent`，它不会自动用 RAG。它只是普通聊天/代码模型。

要用 RAG，有三种方式：

### 方式 A：先用 curl 调 RAG，再把结果贴给 Cline

这是最适合学习阶段的方式。你能看见 search 命中了哪些文档，也能理解 RAG 在干嘛。

### 方式 B：把 Cline 的 Base URL 指向 RAG Service

配置示例：

```text
Base URL: http://82.156.69.153:18010/v1
API Key:  <LABAGENT_RAG_API_KEY>
Model:    labagent-rag
```

这样 Cline 问的是“项目文档问答模型”，它会通过 RAG 回答并附 sources。

限制：当前兼容入口只支持非流式 chat，不适合作为你写代码时的主 Cline 模型。它更适合问项目状态、架构、决策、部署步骤。

### 方式 C：后续做 Agent/MCP 工具

未来更理想的方式是：

```text
Cline / Agent 主模型 = qwen-agent
工具 = rag_search / rag_ask
```

模型需要资料时调用 RAG 工具，而不是把整个 Cline 都切到 RAG Service。这会是后续 Agent Runtime / MCP 节点的目标。

## 10. 你可以这样问 RAG

适合 RAG 的问题：

```text
LabAgent 当前有哪些模型路由？
5090 和新设备分别承担什么角色？
云服务器为什么不能跑 RAG / Agent Runtime？
Qwen3-Coder-30B 为什么被定为 qwen-agent？
RAG v0 当前完成了什么，没完成什么？
下一步路线图是什么？
新设备的 5080 + 4060 Ti 显存应该怎么理解？
```

不适合当前 RAG 的问题：

```text
帮我写一个全新的复杂功能
分析一个不在 docs 里的外部网页
读取 David 本地没有进索引的项目文件
根据图片回答问题
回答实时新闻或模型最新排行
```

原因：当前 RAG 只索引了这个仓库里的 Markdown 文档。

## 11. 怎么判断 RAG 答得好不好

不要只看答案像不像。要分三层：

```text
1. Retrieval：找的资料对不对？
2. Generation：答案有没有忠实使用资料？
3. Citation：引用是不是真的支持这句话？
```

调试顺序：

```text
如果答案错：
  先跑 search 看 top-k
  如果 top-k 没找到正确资料 -> chunking / embedding / query expansion / reranker 问题
  如果 top-k 找到了正确资料但答案错 -> prompt / generation / max_context_chars 问题
  如果答案对但引用乱 -> citation/formatting 问题
```

## 12. 当前边界和下一步

当前仍未完成：

```text
真正的向量数据库：Qdrant / Chroma
hybrid search：向量 + BM25
reranker：对 top-k 二次排序
文档上传 / PDF / 图片 OCR
多用户权限隔离
answer faithfulness 自动评测
MCP / Agent 工具化调用
```

下一步建议：

```text
1. 先用 RAG Service v1 跑通 David/Cline 远程问答
2. 再加 answer eval，验证答案是否忠实引用
3. 再接 reranker
4. 最后把 JSON index 换成 Qdrant / Chroma
```

面试表达重点：

```text
我不是只调用了一个 embedding API，而是实现了从文档切分、向量索引、检索评测、HTTP RAG Service 到带引用回答的最小 RAG 闭环；
并且明确区分 retrieval quality、grounded answer quality 和 citation quality，后续通过 reranker、answer eval 和向量数据库继续迭代。
```
