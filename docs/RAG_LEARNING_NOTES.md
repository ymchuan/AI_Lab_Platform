# RAG 学习与实现笔记

> 目标：边做边学，把 LabAgent 的 RAG 从概念、代码、评测到后续升级路径都记录清楚。

## 1. RAG 是什么

RAG 全称是 Retrieval-Augmented Generation，中文通常叫“检索增强生成”。

它解决的问题是：大模型本身不知道你的私有文档、项目状态、服务器配置和历史决策。RAG 不直接训练模型，而是在回答前先检索你的资料，把相关片段塞进 prompt，再让模型基于这些片段回答。

最小流程：

```text
用户问题
  -> 把问题转成向量
  -> 在知识库里找相似文档片段
  -> 把片段 + 问题交给大模型
  -> 大模型给出带引用的回答
```

## 2. 核心概念

| 概念 | 含义 | 本项目当前对应 |
|------|------|----------------|
| Corpus | 原始资料集合 | `README.md`、`HANDOFF.md`、`docs/*.md` |
| Chunk | 把长文档切成小片段 | `services/rag/chunking.py` |
| Embedding | 把文本转成数字向量 | `embed-local`，Nomic Embed Text v1.5，768 维 |
| Vector Index | 存储 chunk 和向量的索引 | `data/rag/index.json` |
| Retrieval | 根据问题找相似 chunk | cosine similarity top-k |
| Context | 检索出来并塞给模型的证据 | `[S1]`、`[S2]` source blocks |
| Generation | 大模型基于 context 回答 | `qwen-agent` / Qwen3-Coder-30B |
| Citation | 回答里标注证据来源 | `[S1]`、`[S2]` |
| Reranker | 对初筛结果二次排序 | 未接入，后续放新设备 |

## 3. 当前 RAG v0 已实现什么

当前已经完成一个最小可运行闭环：

```text
Markdown 文档
  -> 标题感知 chunk
  -> 调用公网 LiteLLM 的 embed-local
  -> 保存本地 JSON 向量索引
  -> cosine 检索 top-k
  -> 调用 qwen-agent 生成带引用回答
```

代码位置：

```text
services/rag/
├── cli.py          # 命令行入口：index / search / ask
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

## 4. 当前验证结果

2026-06-18：

```text
索引构建：319 chunks / 19 files
embedding：embed-local，768 维
retrieval benchmark：3/3 passed
端到端 ask：可以回答并给出 [Sx] 引用
```

验证过的命令：

```powershell
$env:LABAGENT_BASE_URL = "http://82.156.69.153:8000/v1"
$env:LABAGENT_API_KEY = "<LABAGENT_API_KEY>"
$env:LABAGENT_EMBED_MODEL = "embed-local"
$env:LABAGENT_MODEL = "qwen-agent"

python -m services.rag.cli index
python benchmarks/rag_retrieval_eval.py
python -m services.rag.cli search "LabAgent 当前有哪些公网模型路由？"
python -m services.rag.cli ask "LabAgent 当前多节点路由是什么状态？"
```

本轮实现里的两个实际 RAG 教训：

```text
1. 太短的标题 chunk 会污染 top-k。
   解决：chunking 增加最小证据长度过滤，当前索引从 455 chunks 降到 319 chunks。

2. 纯向量检索对“当前多节点路由状态”这类工程状态问题不够稳。
   解决：对路由/节点/模型/状态问题做 query expansion，并在排序时加入轻量 keyword/entity score。
```

## 5. 重要边界

当前 RAG v0 是学习版和 baseline，不是生产版。

已完成：

```text
文档加载
Markdown chunking
embedding
本地向量索引
相似度检索
带引用回答
retrieval benchmark
```

未完成：

```text
真正的向量数据库
hybrid search
reranker
文档上传 / PDF / 图片 OCR
API Server
权限隔离
answer faithfulness 自动评测
多轮 RAG 记忆
```

一个关键教训：检索命中不等于最终答案一定正确。RAG 质量至少要分三层看：

```text
retrieval 是否找到了正确证据
generation 是否忠实使用证据
citation 是否指向了真实来源
```

当前 `rag_retrieval_eval.py` 主要验证第一层。下一阶段要补第二层和第三层。

## 6. 下一步学习路线

短期按这个顺序推进：

1. 把 RAG v0 固化为可重复命令和文档。
2. 接入真正的向量库，优先 Qdrant 或 Chroma。
3. 新设备接入 reranker，比较“只检索”和“检索 + 重排”的差异。
4. 增加 answer eval：检查回答是否引用、是否幻觉、是否把节点和模型映射错。
5. 提供 FastAPI RAG 服务，让 Agent / MCP / Web UI 都能调用。

面试表达重点：

```text
我不是只调用了一个 embedding API，而是实现了从文档切分、向量索引、检索评测到带引用回答的最小 RAG 闭环；
并且明确区分 retrieval quality、grounded answer quality 和 citation quality，后续通过 reranker 与 answer eval 迭代。
```
