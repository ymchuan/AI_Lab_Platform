# 本地模型选型调研

> 日期：2026-06-18
> 目标：最大化利用 5090 / 5080 新设备两台当前可规划机器，同时服务 Agent 开发、RAG、模型工程和简历展示。8060S 当前无法使用，暂不纳入近期资源池。

## 当前事实基线

| 节点 | 硬件 | 内存 | 当前状态 | 定位 |
|------|------|------|---------|------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB | 已接入 LM Studio，并完成多模型 benchmark；Qwen3-Coder-30B 已定为默认 `qwen-agent` | 主力推理 / Agent 主模型 |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 | 61.4GB | 未接入 | 第二推理 / VL / Embedding / Rerank |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 31.6GB | 当前无法使用 | 冻结近期接入计划 |
| 云服务器 | Ubuntu 24.04, 2 核 2GB | 2GB | LiteLLM 已运行 | 轻量网关 / HTTPS / 隧道 |

重要约束：

1. 云服务器不能升级，也没有预算扩容；它只做 LiteLLM、HTTPS、鉴权和 SSH 隧道中转。
2. OpenWebUI、RAG、Agent Runtime、向量数据库、评测和模型工程实验都应放到本地机器。
3. 当前 5090 的默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` GGUF Q6_K 已定位为 reasoning baseline，不应直接当作最终执行模型。
4. 当前后端存在 `reasoning_content` 过多、`message.content` 为空的问题；这会显著影响 Cline/Agent 工具调用体验。
5. 8060S 当前无法使用，OCR / Whisper / 文档解析不再绑定到 8060S，短期改由新设备或 5090 承担。
6. 新设备可以理解为 32GB 专用显存资源池，但不是一块连续 32GB 显存；Windows 任务管理器显示的共享 GPU 内存不能按 VRAM 使用，模型选型要区分“单卡可跑”和“跨卡需要推理引擎支持”。

## 核心判断

1. **5090 32GB VRAM**：主攻 coding / agent 主模型。当前固定默认 load `qwen/qwen3-coder-30b`，不再把 27B/35B/Gemma/GLM 作为常驻执行模型。
2. **RTX 5080 16GB + RTX 4060 Ti 16GB**：最适合承载 RAG 检索侧模型、轻量/中等第二模型、VL/OCR 实验。Embedding / Reranker 应优先放这里，减少 5090 被小模型占用。两张卡合计 32GB 是专用显存资源池，不代表单个 dense 模型能天然当作 32GB 单卡运行。
3. **8060S**：当前不可用，冻结近期规划。文档解析、OCR、Whisper 等能力后移到新设备或以后新增节点。
4. **简历价值来自“选择 + 评测 + 路由 + 优化”**：每次模型替换都要记录 benchmark、显存、吞吐、失败模式和取舍。

## 推荐模型组合

### 5090：主 Agent / 代码 / 通用推理

5090 主模型已定为 `qwen/qwen3-coder-30b`。其他模型保留为对照或按需切换测试，不建议与主模型长期同时常驻。

| 优先级 | 模型 | 用途 | 部署建议 | 为什么测 |
|--------|------|------|---------|---------|
| P0 (已测) | 当前 `qwen/qwen3.6-27b` GGUF Q6_K | 当前基线 / qwen-think 候选 | reload 后速度改善，但 final `content` 仍经常为空 | 适合作为 reasoning baseline，不适合作为默认 Agent/Cline/RAG 执行模型 |
| P0 (已定) | `qwen/qwen3-coder-30b` | Cline / coding agent 主模型 | 5090 LM Studio 默认 load；后续再测 SGLang/vLLM | 已能稳定返回 `content`，patch 2/2，soft-scoring 后 agent-readiness 信号最好 |
| P0 | Qwen3.6-35B-A3B 量化版 | 通用 + coding + agent 对照 | 5090 上跑 4bit/5bit；记录显存和上下文长度 | 35B-A3B 级别适合 32GB VRAM 做主力模型候选 |
| P0 (已测) | `qwen/qwen3.6-35b-a3b` | 通用 / reasoning 对照 | 2026-06-16 复测仍是 reasoning-only 失败模式，`/no_think` 无效 | 不提升为默认 Agent 执行模型 |
| P0 (已测) | `qwen/qwen3-30b-a3b-2507` | 通用 / planning / patch 对照 | 可保留为对照模型；不作为当前默认 Cline 主模型 | agent_tasks strict 3/4、patch 2/2，但长任务约 110s+，repo map full-context 超时 |
| P1 | Qwen3-Coder-Next | 高阶 coding agent 实验 | GGUF + CPU/GPU 混合卸载；不作为第一稳定服务 | 80B total / 3B active，agentic coding 强，但权重总量对 32GB VRAM 更激进 |
| P1 | DeepSeek-R1-Distill-Qwen-32B | 推理/规划对照 | 量化版，单独测 reasoning 质量 | 适合复杂推理，不一定适合工具调用和 Cline |
| P2 (已测) | zai-org/glm-4.7-flash | 聊天/规划对照 | LM Studio 已测试 raw + `/no_think` 模式 | 2026-06-15 已完成 12 次 benchmark；聊天和规划能力可用，但 patch/repo/Cline 任务失败；不适合当默认 Cline/Agent 主模型 |

**GLM-4.7-Flash 测试结论（2026-06-15 重测）**：重新 load 后延迟大幅改善（3-62s vs 旧 34-76s）。知识问答通过（rag_resume_value 5/5），项目理解接近通过（repo_map_current_state 5/6），agent_recovery 接近通过（3/4）。但 patch 生成仍然 0/10，agent_tool_choice/planning 仍然 0/4。**结论：保留为知识问答/项目理解对照模型，不提升为默认 Cline/Agent 主模型。**

第一轮推荐默认结论：  
**当前阶段结论：`qwen/qwen3-coder-30b` 定为 5090 默认 `qwen-agent`；`qwen/qwen3.6-27b` 和 `qwen/qwen3.6-35b-a3b` 继续作为 reasoning 对照，不进入默认 Cline/Agent 执行路径。**

### 新设备：第二推理 / RAG 检索 / 对照实验

新设备模型选型建议在 5090 候选模型评测完成后再最终确定。初始原则：

- RTX 5080 16GB：优先测能单卡稳定运行的中等代码/通用/VL 模型，作为 `coder-small-local`、`vision-local` 或第二聊天模型。
- 4060 Ti 16GB：优先放 Embedding、Reranker、轻量模型和实验服务。
- 跨 RTX 5080 + RTX 4060 Ti 跑单个大模型只作为进阶实验；需要确认 LM Studio / llama.cpp / vLLM / SGLang 对异构双卡的支持和实际吞吐。

| 优先级 | 模型 | 用途 | 部署建议 |
|--------|------|------|---------|
| P0 | Qwen3-Embedding-4B / 8B | RAG 向量化 | 优先测 4060 Ti；压力大再放 5080 |
| P0 | Qwen3-Reranker-0.6B / 4B | RAG 重排 | 4060 Ti 可承载 0.6B；5080 承载 4B |
| P0 | Qwen2.5-VL-7B / Qwen3-VL 小量化版 | 图片问答 / OCR 后理解 | 5080 单卡优先，用于补足 Qwen3-Coder 非多模态短板 |
| P1 | Devstral-Small 系列或 Qwen3-Coder 小/中量化版 | 第二代码模型 / 对照模型 | 5080 单卡跑，作为 `coder-small-local` |
| P1 | BGE-M3 | 多语言 embedding fallback | CPU/GPU 都可测试 |
| P1 (已测) | `text-embedding-nomic-embed-text-v1.5` | embedding smoke test | LM Studio `/v1/embeddings` 可用，768 维；后续补真实 chunk + rerank benchmark |

建议对外模型别名：

```text
embed-local       -> Qwen3-Embedding
rerank-local      -> Qwen3-Reranker
vision-local      -> 5080 上的 VL / 图片问答模型
coder-small-local -> 5080 上的第二代码模型
```

### 文档处理 / 语音 / OCR（8060S 暂不可用）

| 优先级 | 模型/工具 | 用途 | 部署建议 |
|--------|-----------|------|---------|
| P0 | MinerU | PDF / Office / 图片转 Markdown/JSON | 暂放新设备或 5090 CPU/GPU 空闲时段，输出给 RAG ingestion |
| P0 | PaddleOCR-VL | OCR / 文档版面解析 | 先作为新设备候选任务，做复杂版面、表格、图片文字解析对照 |
| P1 | faster-whisper / Whisper large-v3 系列 | 语音识别 | 后移；等新设备接入后再评估是否部署 |
| P1 | Qwen2.5-VL-7B-Instruct 或轻量 VLM | 图文问答 / 图片理解 | 作为 OCR 后的多模态补充，优先考虑新设备 |

虽然 8060S 暂不可用，但文档处理能力仍是 RAG 数据入口的一部分：  
**文件 -> 解析 -> 清洗 -> chunk -> embedding -> 检索 -> 引用回答。**

## 推理引擎路线

| 阶段 | 引擎 | 目标 | 说明 |
|------|------|------|------|
| 当前 | LM Studio | 快速可用 | 保留，适合探索模型和调试 OpenAI-compatible API |
| 下一步 | llama.cpp / GGUF | 量化和消费级显卡适配 | 适合 Windows、混合卸载、快速试模型 |
| 进阶 | SGLang | Agentic coding、工具调用、结构化输出 | 适合 Qwen / GLM / DeepSeek 等模型的服务化实验 |
| 进阶 | vLLM | 高并发、连续批处理、生产化服务 | 更适合 WSL2/Linux + CUDA，后续用于性能对照 |

## Benchmark 设计

每个候选模型必须跑同一套任务，不能只靠主观聊天体验。

| 维度 | 指标 | 为什么重要 |
|------|------|------------|
| 性能 | first token、tokens/s、总延迟、显存占用 | 证明 5090/5080 是否被充分利用 |
| 输出可用性 | `content` 非空率、`reasoning_content` 比例、finish_reason | 解决当前 Agent 输出不可用问题 |
| Coding | 小型修 bug、生成测试、解释仓库结构 | 贴近 Agent 开发岗 |
| Agent | 工具选择、失败恢复、多步计划 | 证明不是只会聊天 |
| RAG | oracle context、retrieved context、引用准确率 | 证明知识库可用 |
| Cline 工作流 | repo map、patch 生成、多轮上下文稳定性 | 贴近真实 VS Code 项目文件修改体验 |
| 稳定性 | 1 小时连续请求、长上下文、多轮对话 | 证明能长期作为基础设施 |

2026-06-16 校准：

```text
agent_tasks / cline_dialogue 当前属于 Agent-readiness smoke tests，不等同于完整 Agent Runtime benchmark。
0 strict pass 不能直接解释为“模型完全不会 Agent”，而应解释为“不能直接提升为默认 Agent 执行模型”。
后续要补 tool_call_eval、patch_apply_eval、repo_task_eval、rag_retrieval_eval 和 trace_eval。
```

详见 `docs/BENCHMARK_DESIGN.md`。

## 第一轮落地顺序

1. 记录当前 LM Studio 模型画像：`qwen/qwen3.6-27b`、`Qwen3.6-27B-Q6_K.gguf`、GGUF、Q6_K、约 23.01GB、上下文长度、GPU 占用和并行数。
2. 用升级后的 benchmark v2 重跑当前 `qwen/qwen3.6-27b` GGUF Q6_K baseline，重点记录 `content` 非空率、`reasoning_content` 长度、`finish_reason`、repo map、patch 和 Cline 多轮通过率。
3. 继续调 LM Studio preset，验证 thinking / response length / context / KV cache 对 Agent 输出可用性的影响。
4. 5090 固定默认 load Qwen3-Coder 30B，继续补 tool call / patch apply / Cline 多轮 harness。
5. 接入新设备，先部署 Qwen3-Embedding / Qwen3-Reranker，再评估 VL 与第二代码模型。
6. 文档解析 / OCR / Whisper 暂不绑定 8060S，先在新设备接入后评估部署位置。
7. 每轮结果写入 `docs/BENCHMARK_RESULTS.md`，并更新 `README.md` / `HANDOFF.md` / `CHANGELOG.md`。

## 主要参考来源

- Qwen3.6 官方仓库：https://github.com/QwenLM/Qwen3.6
- Qwen3-Coder 官方仓库：https://github.com/QwenLM/Qwen3-Coder
- Qwen3-Coder-Next 模型卡：https://huggingface.co/Qwen/Qwen3-Coder-Next
- Qwen3 Embedding / Reranker：https://qwenlm.github.io/blog/qwen3-embedding/
- Qwen3-Embedding GitHub：https://github.com/QwenLM/Qwen3-Embedding
- vLLM OpenAI-compatible serving：https://docs.vllm.ai/en/stable/serving/online_serving/
- SGLang OpenAI-compatible API：https://docs.sglang.ai/basic_usage/openai_api_completions.html
- llama.cpp / GGUF：https://github.com/ggml-org/llama.cpp
- MinerU：https://github.com/opendatalab/mineru
- PaddleOCR / PaddleOCR-VL：https://github.com/PaddlePaddle/PaddleOCR
- faster-whisper：https://github.com/SYSTRAN/faster-whisper
- Qwen2.5-VL：https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
