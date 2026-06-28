# Code Review 分流记录

> 记录 LabAgent 对外部 AI review 的采纳、后置和拒绝决定。
> 原始 review 作为本地参考保留，不作为项目源事实。

## 2026-06-22 分流

### 立即采纳

| 领域 | 决策 | 结果 |
|------|------|------|
| Benchmark 默认 URL | 有效问题 | 源码默认值改成 `http://127.0.0.1:8000/v1`，公网云地址只在文档和 env 示例里显式写出。 |
| Streaming 错误处理 | 有效问题 | `benchmarks/common.py` 现在会把畸形 streaming chunk 和缺失字段当成结构化失败结果，而不是直接崩掉。 |
| `max_tokens_override` 假值 bug | 有效问题 | Benchmark 脚本现在区分 `None` 和 `0`，CLI 覆盖值会被精确执行。 |
| RAG chunking 参数 | 有效问题 | `split_markdown` 现在会校验 `max_chars` 和 `overlap_chars`。 |
| RAG 索引完整性 | 有效问题 | `load_index` 现在会检查 index version、embedding model、chunk count、embedding 维度元数据，以及每个 chunk 的向量维度。 |
| RAG CLI 路径清晰度 | 有效问题 | `index` 现在支持 `--root`；`search` 和 `ask` 在缺少 index 时会更早报出清晰错误。 |
| 原始 prompt / review 污染 | 新发现问题 | `docs/CODE_REVIEW_ISSUES.md` 和 `docs/claude-fable-5.md` 已加入 ignore，并排除出默认 RAG discovery。 |

### 推迟

| 领域 | 原因 |
|------|------|
| 用向量数据库替换 JSON index | 这是 RAG Service v1 的工作，不是一次小硬化补丁能完成的。 |
| 去重所有 cosine helper | 风险较低，等 eval harness 重组时再清理。 |
| 重写所有 benchmark prompts | 许多历史 benchmark 文件保留着旧上下文；prompt 清理应该跟着新的 benchmark 版本一起做。 |
| 构建生产级 Agent runtime | 这仍然是 RAG Service v1 基础设施之后的下一个大里程碑。 |

### 拒绝

| 建议 | 原因 |
|------|------|
| 从所有文档里删掉公网网关 URL | 公网 URL 是刻意保留的部署事实。它不该是源码默认值，但应该出现在 setup 和 API 文档里。 |
| 提交原始第三方系统 prompt 材料 | 这会污染 RAG 和项目文档。保留在本地参考里，只提交 LabAgent 自己总结出来的内容。 |

## 验证要求

后续做完 code review 硬化后，建议跑：

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m services.rag.cli search "test" --index-path data/rag/missing.json
git diff --check
git status --short --ignored
```
