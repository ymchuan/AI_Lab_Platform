# Agent Router 学习笔记

> 这份笔记解释 `labagent-agent` 在做什么、为什么要做，以及它和真正 Agent Runtime 的差别。

## 1. 为什么要有 router

如果所有请求都直接打到一个模型，后面会遇到三个问题：

1. 图片和文本混在一起时，纯代码模型不一定能看图。
2. 项目知识问答如果不检索文档，回答容易没有引用依据。
3. 推理、编码、OCR、检索这几类任务的最佳模型不一定是同一个。

router 的作用是把一个用户请求先拆开判断：

```text
有没有图片 -> 需要 vision-local 吗？
是不是项目知识问题 -> 需要 RAG Service 吗？
最后由谁组织给用户看的答案 -> qwen-agent
```

这样外部客户端仍然只看到一个模型名 `labagent-agent`，但内部可以组合多个本地能力。

## 2. 当前 router 不是完整 Agent Runtime

现在的 `services/agent` 只是一个编排层，不做自主执行。

它会做：

- 识别 OpenAI `image_url` / `input_image` 内容块。
- 识别 LabAgent 项目相关问题。
- 调用 `vision-local` 或 RAG Service。
- 把 side channel 结果交给 `qwen-agent` 生成最终回答。

它不会做：

- 自己规划多步任务。
- 执行 shell、读写文件或应用 patch。
- 维护长期 memory。
- 自动重试复杂失败。
- 真正 token-by-token streaming；当前只有 SSE 兼容降级。

所以它更像“路由器 + 汇总器”，不是会自己干活的完整智能体。

## 3. 当前模型分工

```text
labagent-agent
  -> qwen-agent: 普通文本、代码/工程回答、最终对外输出
  -> vision-local: 图片问答、截图理解、OCR-ish 文字提取
  -> RAG Service: 项目文档检索、历史状态、引用证据
```

`qwen-think` 当前只是未来 brain/reasoning 候选，还没有接进 router 路径。这样做是因为之前 benchmark 里它的最终 `content` 稳定性不如 `qwen-agent`，暂时不适合直接作为团队默认执行入口。

## 4. “brain / eyes / hands” 怎么理解

可以先这样理解：

- brain: 复杂推理和规划，未来可以接 `qwen-think`。
- eyes: 识图、读截图、OCR，目前是 `vision-local`。
- hands: 写代码、改文件、执行工具，目前仍由客户端如 Cline/Codex CLI 负责。
- voice: 最终回答用户，目前是 `qwen-agent`。

当前 v0 router 只真正接入了 eyes、RAG 和 voice；brain 与 hands 还没有做成自动闭环。

## 5. 图片为什么走 `vision-local`

OpenAI-compatible 图片请求通常长这样：

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "请描述这张图片"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  ]
}
```

router 发现 `image_url` 后会先调用 `vision-local`，要求它提取：

- 图片里的文字。
- UI 状态和错误提示。
- 表格、代码片段、文件名。
- 颜色、形状、布局关系。

然后 router 再把这个视觉摘要交给 `qwen-agent`，让它用用户的语言组织最终回答。

2026-06-29 本地 smoke 结果：

```text
route=image_input
vision_model=vision-local
vision_summary=读出 "VISION TEST 42"、blue block、green block、左上/右下布局
final=qwen-agent 用中文给出简短描述
```

这说明“外部看起来一个模型，内部先看图再回答”的基础链路已经跑通。

## 6. RAG 为什么单独一层

RAG 不只是“多塞一些文档给模型”。它负责：

1. 把项目文档切块。
2. 把 chunk 转成 embedding。
3. 在索引里找相关片段。
4. 把片段和来源交给模型。

所以 RAG 的重点是证据，而不是聊天。

当前 router 只要命中 LabAgent / 项目关键词，就会先问 RAG Service。如果 RAG 失败，router 会把失败原因交给 `qwen-agent`，避免模型假装已经查到资料。

## 7. 运行位置

当前实际运行位置：

```text
5090:
  - LM Studio: qwen-agent
  - RAG Service: 127.0.0.1:8010
  - Agent Router: 127.0.0.1:8020
  - SSH :12340 -> 云端 LiteLLM 回连 5090 LM Studio
  - SSH :18020 -> 云端公网入口回连 8020

新设备:
  - LM Studio: embed-local + vision-local
  - SSH :12341 -> 云端 LiteLLM 回连新设备 LM Studio

云服务器:
  - LiteLLM: 82.156.69.153:8000
  - SSH 隧道中转
```

`embed-local` 当前经 LiteLLM 路由到新设备，不是 5090 的本地 embedding。即使 5090 LM Studio 也加载了 embedding 模型，只要 RAG/agent 配置使用 `http://82.156.69.153:8000/v1` + `embed-local`，实际就走云端 LiteLLM -> 新设备 `:12341`。

## 8. 当前验证状态

2026-06-29 已验证：

- `.env.local` 已补 `LABAGENT_AGENT_API_KEY`，它和 `LABAGENT_API_KEY`、`LABAGENT_RAG_API_KEY` 分离。
- 本地 `GET http://127.0.0.1:8020/health` 正确 key 返回 200，错误 key 返回 401。
- direct chat 分支返回 200，route=`direct_chat`。
- RAG 分支返回 200，route=`project_context`，`rag_ok=true`。
- 图片分支返回 200，route=`image_input`，能调用 `vision-local` 并由 `qwen-agent` 汇总。
- 云端已看到 `0.0.0.0:18020` 监听，云服务器本机 `curl 127.0.0.1:18020/health` 通过。
- 腾讯云安全组放行 TCP 18020 后，公网 `/health`、`/v1/models` 和 direct chat 已验证 200。
- Cline 报过 `labagent-agent does not support stream=true yet`，router 已增加 SSE 兼容降级：先完整生成回答，再按 OpenAI chunk 事件返回。

未完成：

- LM Studio 升级后模型暂未重新 load，所以还没有复测 Cline 远程图片请求。
- 当前 SSE 只是兼容客户端的返回格式，还不是边生成边输出的真流式。

## 9. 当前边界

- `stream=true` 已做 SSE 兼容降级，但不是真正 token-by-token streaming。
- 还不是 tool-calling agent。
- RAG 和 vision 都是 side channel，不是可自动循环的 planner。
- 路由规则还是关键词和内容块判断，后续可以升级为 intent classifier。
- 公网入口仍靠手动 SSH 隧道，不是生产常驻服务。

下一步更合理的方向：

1. 先从 Cline 远程验证 `labagent-agent` 的普通文本和图片请求。
2. 修 RAG v1.x 的检索质量、reranker 和 answer faithfulness。
3. 再把 router 升级到真正 streaming、错误恢复、trace 和工具注册表。
