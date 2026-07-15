# 本地模型选型调研

> 日期：2026-07-03
> 目标：最大化利用 5090 / 5080 新设备 / 8060S 三类本地资源，同时服务团队开发、RAG、模型工程和求职项目展示。8060S 已恢复为候选节点，但尚未接入公网路由，必须先 benchmark 再提升角色。

## 当前事实基线

| 节点 | 硬件 | 内存 | 当前状态 | 定位 |
|------|------|------|---------|------|
| 5090 | RTX 5090 32GB + AMD Radeon 610M | 93.7GB | 已接入 LM Studio，并完成多模型 benchmark；Qwen3-Coder-30B 已定为默认 `qwen-agent` | 主力推理 / Agent 主模型 |
| 新设备 | RTX 5080 16GB + RTX 4060 Ti 16GB + AMD 集显 | 61.4GB | `embed-local` / `vision-local` 已接入 | Embedding 和 Vision 已上线；第二推理 / Rerank 待接入 |
| 8060S | AMD Ryzen AI MAX+ 395 / Radeon 8060S / NPU | 63.65GB（2026-07-15 本机 smoke 实测） | 模型库存可达，但指定 35B chat 全部 HTTP 400；未接入 LiteLLM / `:12342` | 候选 brain / 文档处理 / rerank / 轻量服务节点 |
| 云服务器 | Ubuntu 24.04, 2 核 2GB | 2GB | LiteLLM 已运行 | 轻量网关 / HTTPS / 隧道 |

重要约束：

1. 云服务器不能升级，也没有预算扩容；它只做 LiteLLM、HTTPS、鉴权和 SSH 隧道中转。
2. OpenWebUI、RAG、Agent Runtime、向量数据库、评测和模型工程实验都应放到本地机器。
3. 当前 5090 的默认 Agent/Cline 执行模型定为 `qwen/qwen3-coder-30b`；`qwen/qwen3.6-27b` GGUF Q6_K 已定位为 reasoning baseline，不应直接当作最终执行模型。
4. 当前后端存在 `reasoning_content` 过多、`message.content` 为空的问题；这会显著影响 Cline/Agent 工具调用体验。
5. 8060S 已恢复，但不能因为“可用”就直接承担主路由；先验证 LM Studio 本机吞吐、OpenAI-compatible 兼容性、隧道稳定性、输出 `content` 可用性和 Codex smoke。
6. 新设备可以理解为 32GB 专用显存资源池，但不是一块连续 32GB 显存；Windows 任务管理器显示的共享 GPU 内存不能按 VRAM 使用，模型选型要区分“单卡可跑”和“跨卡需要推理引擎支持”。

## 核心判断

1. **5090 32GB VRAM**：主攻 coding / agent 主模型。当前固定默认 load `qwen/qwen3-coder-30b`，不再把 27B/35B/Gemma/GLM 作为常驻执行模型。
2. **RTX 5080 16GB + RTX 4060 Ti 16GB**：最适合承载 RAG 检索侧模型、轻量/中等第二模型、VL/OCR 实验。当前已接入 `text-embedding-nomic-embed-text-v1.5-embedding` 作为 `embed-local`，并接入 `qwen/qwen3-vl-30b` 作为 `vision-local`，减少 5090 被非代码主任务占用。两张卡合计 32GB 是专用显存资源池，不代表单个 dense 模型能天然当作 32GB 单卡运行。
3. **8060S**：已恢复为候选节点。AMD Ryzen AI Max+ 395 / Radeon 8060S 的优势是统一内存形态、较大的可用系统内存窗口和本地 AI/多媒体任务弹性；短板是当前 LabAgent 主栈以 Windows + LM Studio + CUDA 稳定路径为主，AMD/Vulkan/ROCm/llama.cpp/vLLM 的实际吞吐与兼容性必须本机验证。因此 8060S 先做新增实验路由，不直接替换 5090 主代码模型。
4. **简历价值来自“选择 + 评测 + 路由 + 优化”**：每次模型替换都要记录 benchmark、显存、吞吐、失败模式和取舍。

## 2026-07-03 联网调研后的 8060S 架构判断

调研来源主要看官方资料：AMD Ryzen AI Max+ 395 规格页、AMD Radeon/Ryzen 的 ROCm 文档、NVIDIA RTX 5090 规格页，以及当前项目本地已跑过的 benchmark。结论不是“8060S 不行”，而是“8060S 不能直接抢主路径”。

核心判断：

1. 5090 仍应保留 `qwen-agent` / Qwen3-Coder-30B。团队成员用 Codex/Cline 写代码时，最重要的是稳定返回 `message.content`、patch 可用、工具链错误少；当前这些证据都来自 5090 + Qwen3-Coder。
2. 8060S 更适合先做 `brain-local` / `doc-local` / `rerank-local` 候选。它可以承担推理总结、文档解析、OCR/Whisper、rerank、轻量模型和长上下文实验，但要先证明延迟、吞吐和输出格式稳定。
3. 新设备继续保留 `embed-local` / `vision-local`。图片链路刚恢复成功，不建议因为 qwen3.6 能看图就立刻替换 `vision-local`；多模态“能看见”和“代码截图 OCR 准确”是两回事。
4. 用户提出的“5090 做 brain，8060S 做 coder worker，5080/4060Ti 做 eyes/embedding”概念上很像分工式 agent，但当前风险在于把最重要的 coding worker 放到未评测节点。更稳的阶段性版本是：5090 = coding worker + final answer，8060S = optional brain side-channel，新设备 = eyes + embedding。

推荐候选路由：

```text
qwen-agent       -> 5090 / Qwen3-Coder-30B（团队默认 coding worker，不动）
vision-local     -> 新设备 / Qwen3-VL-30B（图片、截图、OCR-ish）
embed-local      -> 新设备 / Nomic embedding（RAG 向量化）
brain-local      -> 8060S 候选 / qwen3.6 或其他 reasoning 模型（先旁路）
doc-local        -> 8060S 候选 / OCR、Whisper、文档解析
rerank-local     -> 8060S 或新设备候选 / reranker
coder-small-local -> 8060S 或新设备候选 / 中小代码模型，通过 smoke 后再暴露
```

8060S 提升为默认角色前必须通过：

1. 本机 `curl http://127.0.0.1:1234/v1/models` 和最小 chat。
2. 云端 `:12342` 隧道和 LiteLLM `/v1/models` / `/v1/chat/completions`。
3. `model_latency.py`：记录 first token、总延迟、tokens/s、`content` 非空率、finish reason。
4. Codex smoke：至少 C1/C2/C4/C6，确认 read/write/multi-file/test recovery 能跑。
5. `patch_task_eval.py` 和 `repo_map_eval.py`：证明它不是只会聊天。
6. 30-60 分钟稳定性：连续请求不掉线、不空内容、不明显 OOM。

2026-07-15 首轮结果：`GET /v1/models` 成功，但 `qwen3.6-35b-a3b-uncensored` 的 5 个 chat case 全部返回 HTTP 400，未产生 `content` 或 `reasoning_content`。这属于模型加载/服务请求层失败，不是能力得分；8060S 继续保持候选状态，确认 LM Studio 实际加载实例后再复测。

当前已有一键 smoke 脚本：

```powershell
# 在 8060S 机器上运行，前提是 LM Studio 已 load 目标模型并开启 Local Server
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_8060s_brain_smoke.ps1 -TimeoutSec 600 -MaxTokens 512
```

脚本位置：`benchmarks/run_8060s_brain_smoke.ps1`。它会生成 `8060s_smoke_results/8060s_smoke_<timestamp>/`，包含 Markdown 汇总、JSON 报告和 raw responses。第一轮重点看 `content_length` 是否非空、`reasoning_length` 是否过长、`finish_reason` 是否为 `length`、中文 300-500 字稳定性和可选图片识别是否通过。

## 推荐模型组合

### 5090：主 Agent / 代码 / 通用推理

5090 主模型已定为 `qwen/qwen3-coder-30b`。其他模型保留为对照或按需切换测试，不建议与主模型长期同时常驻。

| 优先级 | 模型 | 用途 | 部署建议 | 为什么测 |
|--------|------|------|---------|---------|
| P0 (已测) | 当前 `qwen/qwen3.6-27b` GGUF Q6_K | 当前基线 / qwen-think 候选 | reload 后速度改善，但 final `content` 仍经常为空 | 适合作为 reasoning baseline，不适合作为默认 Agent/Cline/RAG 执行模型 |
| P0 (已定) | `qwen/qwen3-coder-30b` | Cline / coding agent 主模型 | 5090 LM Studio 默认 load；后续再测 SGLang/vLLM | 已能稳定返回 `content`，patch 2/2，soft-scoring 后 agent-readiness 信号最好 |
| P0 (已测) | `qwen3.6-27b-uncensored@?` | experimental brain/eyes | 5090 LM Studio 直连；可通过 `LABAGENT_AGENT_BRAIN_MODEL` 作为 side channel | 能识图和完成极短回答，但长文本 `content` 不稳定、延迟高；不替换 `qwen-agent` 或 `vision-local` |
| P0 | Qwen3.6-35B-A3B 量化版 | 通用 + coding + agent 对照 | 5090 上跑 4bit/5bit；记录显存和上下文长度 | 35B-A3B 级别适合 32GB VRAM 做主力模型候选 |
| P0 (已测) | `qwen/qwen3.6-35b-a3b` | 通用 / reasoning 对照 | 2026-06-16 复测仍是 reasoning-only 失败模式，`/no_think` 无效 | 不提升为默认 Agent 执行模型 |
| P0 (已测) | `qwen/qwen3-30b-a3b-2507` | 通用 / planning / patch 对照 | 可保留为对照模型；不作为当前默认 Cline 主模型 | agent_tasks strict 3/4、patch 2/2，但长任务约 110s+，repo map full-context 超时 |
| P1 | Qwen3-Coder-Next | 高阶 coding agent 实验 | GGUF + CPU/GPU 混合卸载；不作为第一稳定服务 | 80B total / 3B active，agentic coding 强，但权重总量对 32GB VRAM 更激进 |
| P1 | DeepSeek-R1-Distill-Qwen-32B | 推理/规划对照 | 量化版，单独测 reasoning 质量 | 适合复杂推理，不一定适合工具调用和 Cline |
| P2 (已测) | zai-org/glm-4.7-flash | 聊天/规划对照 | LM Studio 已测试 raw + `/no_think` 模式 | 2026-06-15 已完成 12 次 benchmark；聊天和规划能力可用，但 patch/repo/Cline 任务失败；不适合当默认 Cline/Agent 主模型 |

**GLM-4.7-Flash 测试结论（2026-06-15 重测）**：重新 load 后延迟大幅改善（3-62s vs 旧 34-76s）。知识问答通过（rag_resume_value 5/5），项目理解接近通过（repo_map_current_state 5/6），agent_recovery 接近通过（3/4）。但 patch 生成仍然 0/10，agent_tool_choice/planning 仍然 0/4。**结论：保留为知识问答/项目理解对照模型，不提升为默认 Cline/Agent 主模型。**

第一轮推荐默认结论：  
**当前阶段结论：`qwen/qwen3-coder-30b` 定为 5090 默认 `qwen-agent`；`qwen/qwen3.6-27b` 和 `qwen/qwen3.6-35b-a3b` 继续作为 reasoning 对照，不进入默认 Cline/Agent 执行路径。**

**`qwen3.6-27b-uncensored@?` 快速测试结论（2026-06-29）**：

| 任务 | 结果 | 备注 |
|------|------|------|
| 英文极短回答 `brain-ok` | 通过，约 28s | `content=brain-ok`，同时产生约 518 chars `reasoning_content` |
| 中文 RAG 解释，500 tokens | 失败 | `finish_reason=length`，`content` 为空，`reasoning_content` 约 1787 chars |
| 中文 RAG 解释，1500 tokens | 失败 | 约 240s 超时 |
| 简单 Python `add(a,b)` | 通过，约 48s | 能产出代码，但延迟明显高于主力 coder |
| 图片 OCR/形状识别 | 通过，约 38s | 识别 `VISION 73`、蓝色矩形和红色圆形 |

结论：它可以作为“多模态 brain/eyes 实验模型”保留，并通过 `labagent-agent` 的 brain side channel 接入；但不建议替换当前 `qwen-agent` 或 `vision-local`。主要原因是 final `message.content` 不稳定、延迟高、容易把输出预算花在 reasoning 上。代码截图识别也不能替代读取真实源文件。

### 新设备：第二推理 / RAG 检索 / 对照实验

新设备模型选型建议在 5090 候选模型评测完成后再最终确定。初始原则：

- RTX 5080 16GB：优先测能单卡稳定运行的中等代码/通用/VL 模型，作为 `coder-small-local`、`vision-local` 或第二聊天模型。
- 4060 Ti 16GB：优先放 Embedding、Reranker、轻量模型和实验服务。
- 跨 RTX 5080 + RTX 4060 Ti 跑单个大模型只作为进阶实验；需要确认 LM Studio / llama.cpp / vLLM / SGLang 对异构双卡的支持和实际吞吐。

| 优先级 | 模型 | 用途 | 部署建议 |
|--------|------|------|---------|
| P0 (已接入 v1) | text-embedding-nomic-embed-text-v1.5-embedding | RAG 向量化 / 多节点路由验证 | 新设备 LM Studio + SSH `:12341` + LiteLLM `embed-local` |
| P0 | Qwen3-Embedding-4B / 8B | RAG 向量化对照 | 优先测 4060 Ti；压力大再放 5080 |
| P0 | Qwen3-Reranker-0.6B / 4B | RAG 重排 | 4060 Ti 可承载 0.6B；5080 承载 4B |
| P0 (已接入 v1) | qwen/qwen3-vl-30b | 图片问答 / 截图理解 / OCR-ish | 新设备 LM Studio + SSH `:12341` + LiteLLM `vision-local`；2026-06-26 最小公网 smoke 已通过，待固化 VL benchmark |
| P1 | Devstral-Small 系列或 Qwen3-Coder 小/中量化版 | 第二代码模型 / 对照模型 | 5080 单卡跑，作为 `coder-small-local` |
| P1 | BGE-M3 | 多语言 embedding fallback | CPU/GPU 都可测试 |
| P1 (已测) | `text-embedding-nomic-embed-text-v1.5` | embedding smoke test | LM Studio `/v1/embeddings` 可用，768 维；后续补真实 chunk + rerank benchmark |

建议对外模型别名：

```text
embed-local       -> 当前 Nomic Embed Text v1.5；后续与 Qwen3-Embedding 对照
rerank-local      -> Qwen3-Reranker
vision-local      -> 5080 上的 VL / 图片问答模型
coder-small-local -> 5080 上的第二代码模型
```

### 8060S：候选 brain / 文档处理 / Rerank 节点

| 优先级 | 模型/工具 | 用途 | 部署建议 |
|--------|-----------|------|---------|
| P0 | LM Studio + 待定 reasoning 模型 | `brain-local` 旁路总结、复杂问题拆解 | 先通过 `:12342` 暴露为候选 alias，只由 router 按需调用，不进默认团队路径 |
| P0 | Qwen3-Reranker / BGE Reranker | RAG 重排 | 与新设备 4060 Ti 对照，选择延迟和吞吐更稳的一侧 |
| P1 | MinerU | PDF / Office / 图片转 Markdown/JSON | 适合做 RAG ingestion 的文档解析节点，输出 Markdown/JSON 给 workspace index |
| P1 | PaddleOCR-VL | OCR / 文档版面解析 | 做复杂版面、表格、图片文字解析对照；代码截图仍要提醒不可靠 |
| P1 | faster-whisper / Whisper large-v3 系列 | 语音识别 | 可作为团队会议/语音材料入库的实验链路 |
| P2 | 中小代码模型 | `coder-small-local` / 低成本并发 worker | 只有通过 Codex smoke 和 patch eval 后才暴露给团队 |

文档处理能力仍是 RAG 数据入口的一部分：
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
`rag_retrieval_eval.py` 已完成第一版，当前验证真实项目 Markdown 检索 3/3 通过。后续要补 tool_call_eval、patch_apply_eval、repo_task_eval、rag_answer_eval 和 trace_eval。
```

详见 `docs/quality/BENCHMARK_DESIGN.md`。

## 第一轮落地顺序

1. 记录当前 LM Studio 模型画像：`qwen/qwen3.6-27b`、`Qwen3.6-27B-Q6_K.gguf`、GGUF、Q6_K、约 23.01GB、上下文长度、GPU 占用和并行数。
2. 用升级后的 benchmark v2 重跑当前 `qwen/qwen3.6-27b` GGUF Q6_K baseline，重点记录 `content` 非空率、`reasoning_content` 长度、`finish_reason`、repo map、patch 和 Cline 多轮通过率。
3. 继续调 LM Studio preset，验证 thinking / response length / context / KV cache 对 Agent 输出可用性的影响。
4. 5090 固定默认 load Qwen3-Coder 30B，继续补 tool call / patch apply / Cline 多轮 harness。
5. 新设备已完成 `embed-local` 和 `vision-local` v1 接入，真实 RAG retrieval benchmark 已完成 v0；`vision-local` 已通过最小图片/OCR smoke。下一步部署 Qwen3-Embedding / Qwen3-Reranker 对照，补 answer faithfulness / citation eval，并把 VL smoke 固化为图片问答、截图理解和 OCR-ish benchmark。
6. 8060S 接入顺序：先 LM Studio 本机 smoke，再开 `ssh -N -R 12342:127.0.0.1:1234 ...`，再加 LiteLLM alias，最后跑 latency + Codex smoke + patch/repo eval。未通过前不替换 `qwen-agent`。
7. 文档解析 / OCR / Whisper 可重新考虑放 8060S，但必须和新设备方案做同一套吞吐、稳定性和易维护性对照。
8. 每轮结果写入 `docs/quality/BENCHMARK_RESULTS.md`，并更新 `README.md` / `HANDOFF.md` / `CHANGELOG.md`。

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
- AMD Ryzen AI Max+ 395 官方规格：https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html
- AMD ROCm Radeon / Ryzen 文档：https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/
- NVIDIA GeForce RTX 5090 官方页面：https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/
