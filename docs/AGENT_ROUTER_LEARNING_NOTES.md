# Agent Router 学习笔记

> 这份笔记解释 `labagent-agent` 在做什么，以及它为什么还不是完整的 Agent Runtime。

## 1. 为什么要有 router

如果所有请求都直接打到一个模型，后面会有三个问题：

1. 图片和文本混在一起，模型可能看不到图。
2. 项目知识和普通聊天混在一起，回答会缺少引用。
3. 推理、编码、OCR、检索这几件事的最佳模型不一样。

router 的作用就是把一个请求拆开，先决定要不要走视觉、要不要查 RAG，最后再交给主模型收口。

## 2. 这个 router 不是 Agent Runtime

现在的 `services/agent` 只做编排，不做自主执行。

它会做的事：

- 识别图片内容块。
- 识别 LabAgent 项目相关问题。
- 调用 `vision-local` 或 RAG Service。
- 把 side channel 的结果交给 `qwen-agent` 生成最终回答。

它不会做的事：

- 不会自己规划多步任务。
- 不会执行 shell、读写文件或 patch。
- 不会维护长期 memory。
- 不会自动重试复杂失败。
- 不支持 streaming。

## 3. 为什么最终出口还是 `qwen-agent`

`qwen-agent` 当前承担的是“对外工程回答”的角色。

router 的设计是：

- `qwen-think` 用来想。
- `vision-local` 用来看图。
- RAG 用来找项目事实。
- `qwen-agent` 用来把这些输入整理成最终答复。

这样做的好处是，客户端始终看到一个稳定的模型名，但内部可以逐步升级 side channel。

## 4. `qwen-think` 应该放哪里

你可以把 `qwen/qwen3.6-27b` 理解成“脑子更大，但不适合直接做默认执行口”的模型。

它更适合：

- 复杂推理分析。
- 规划。
- 长链条思考。

它不适合现在直接当默认 Agent 主模型的原因是：

- 之前的 benchmark 显示 final content 不稳定。
- 有时会把预算花在 reasoning 上，最后输出不够稳定。
- 对 Cline / Codex / Claude Code 的工作流兼容性还没有证明比 `qwen-agent` 更好。

所以当前策略是：

- `qwen-think` 保留为思考侧模型。
- `qwen-agent` 保留为执行和最终回答模型。

## 5. 图片为什么要走 `vision-local`

图片消息和文字消息不是一回事。

如果请求里有 `image_url`，router 会先把消息送到 `vision-local`，让它提取：

- 图片里的文字。
- UI 状态。
- 错误提示。
- 截图里的表格或代码片段。

然后 router 再把这个摘要交给 `qwen-agent`。

这样做比直接让文本模型猜图更稳。

## 6. RAG 为什么还是单独一层

RAG 不只是“多喂一些文档给模型”。

它做的是：

1. 把项目文档切块。
2. 把块变成 embedding。
3. 在索引里找相关片段。
4. 把片段和来源交给模型。

所以 RAG 的重点是“证据”，不是“聊天”。

当前 router 里只要命中 LabAgent / 项目关键词，就会先问 RAG Service。若 RAG 本身失败，router 会把失败原因一起交给 `qwen-agent`，避免假装已经查到资料。

## 7. 现在这套 router 的边界

- 是一个清晰、可测的 v0 编排层。
- 适合图文问答和项目知识问答。
- 适合作为团队客户端的统一入口。
- 还不是完整智能体。

下一阶段才是：

- planner。
- tool registry。
- file / shell / patch 工具。
- memory 和 trace。
- streaming。
- 更聪明的 intent 分类器或路由器。

## 8. 当前资源分工

- 5090: `qwen-agent` + `qwen-think` 的主推理节点。
- 新设备: `embed-local` + `vision-local`。
- 云服务器: 只做 LiteLLM 和轻量中转。
- RAG Service: 跑在 5090 本地。

这也是为什么“看起来像一个模型”，但实际是多个节点协作。
