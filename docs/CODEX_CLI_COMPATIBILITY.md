# Codex CLI 兼容性验证

> 当前目标：把 LabAgent 从“公网模型能调用”推进到“团队成员能稳定用 Codex CLI 做开发”。

## 结论先行

当前推荐团队默认入口：

```text
Base URL: http://82.156.69.153:8000/v1
Model:    qwen-agent
Auth:     <LABAGENT_API_KEY>
wire_api: responses
```

`qwen-agent` 直连 LiteLLM 是第一阶段主线。`labagent-agent` 暂时是 RAG / Vision / Brain side-channel 的实验入口，不作为 Codex CLI 的默认团队后端。

## 为什么 Codex CLI 是当前 P0

团队真实需求不是只和模型聊天，而是：

```text
成员安装 Codex CLI
  -> 配置 LabAgent base_url + key
  -> 在自己的项目目录里读文件、改代码、跑测试、修失败
```

所以兼容性不能只看 `/v1/models` 或一句 chat 是否返回。要看它能不能完成真实 coding workflow。

## David 机器已通过的 smoke

| 场景 | 状态 | 说明 |
|------|------|------|
| plain chat | 已通过 | 能返回 Qwen-backed answer |
| read-only shell | 已通过 | 能调用 `Get-ChildItem -Force` 并总结目录 |
| create file | 已通过 | 能创建 `hello_labagent.txt` |
| single-file Python patch | 已通过 | 能给 `app.py` 添加类型标注和 `__main__` 示例 |

当前仍未认证：

- multi-file edit
- run tests
- failing test recovery
- long context repo task
- tunnel down / model not loaded / wrong key 的错误体验
- `labagent-agent` 作为 Codex 后端时的行为

## 推荐配置

David / 团队成员的 Codex 配置建议使用自定义 provider。示例：

```toml
model_provider = "LabAgent"
model = "qwen-agent"
disable_response_storage = true

[model_providers.LabAgent]
name = "LabAgent"
base_url = "http://82.156.69.153:8000/v1"
wire_api = "responses"
requires_openai_auth = true
```

API key 使用本机环境或 Codex 支持的本地密钥配置，不要写入仓库文档。

如果 Codex 提示 `Model metadata for qwen-agent not found`，这是自定义模型别名的预期 warning。只要任务能执行并返回结果，就不算失败。

## 手工验收矩阵

建议在 `benchmarks/fixtures/codex_cli_smoke` 的临时副本里执行，避免污染仓库 fixture。

| ID | 任务 | 期望结果 | 当前状态 |
|----|------|----------|----------|
| C0 | `ping` / 简短问答 | 返回非空自然语言内容 | 已通过 |
| C1 | 读取目录和文件 | 能列目录并准确说明文件用途 | 已通过基础版 |
| C2 | 创建新文件 | 生成指定文件，内容准确 | 已通过基础版 |
| C3 | 单文件修改 | 修改 `app.py`，保持测试通过 | 已通过基础版 |
| C4 | 多文件修改 | 同时修改 `app.py` 和 `tests/test_app.py`，测试通过 | 待测 |
| C5 | 运行测试 | 主动执行 `python -m unittest discover` 并解释结果 | 待测 |
| C6 | 失败修复 | 先看到失败测试，再定位并修复 | 待测 |
| C7 | 长上下文 | 阅读 README + 代码 + 测试后做小改动 | 待测 |
| C8 | 后端异常 | wrong key / tunnel down / model unloaded 时错误清楚 | 待测 |
| C9 | `labagent-agent` 后端 | 用 `http://82.156.69.153:18020/v1` + `labagent-agent` 跑 C0-C3 | 待测 |

通过标准：

- 文件最终内容符合任务。
- 测试通过。
- 没有改无关文件。
- 失败时错误信息能让团队成员判断是 key、隧道、模型还是客户端配置问题。

## Fixture 使用方式

在任意机器上复制 fixture 到临时目录：

```powershell
Copy-Item -Recurse <repo>\benchmarks\fixtures\codex_cli_smoke F:\goai\codex_cli_smoke_run
cd F:\goai\codex_cli_smoke_run
python -m unittest discover -s tests -p "test_*.py"
```

初始测试应该通过。然后让 Codex CLI 执行 `TASKS.md` 里的任务。

建议一次只跑一个任务，并记录：

- Codex CLI 版本
- 配置片段（不要贴 key）
- 后端模型：`qwen-agent` 或 `labagent-agent`
- 是否调用工具
- 改了哪些文件
- 测试是否通过
- 失败信息

## 推荐推进顺序

1. 先把 C0-C6 在 David 机器上跑完，证明 `qwen-agent` 能支撑真实小项目开发。
2. 再测试 C8，确认错误体验可接受。
3. 然后用 `labagent-agent` 跑 C0-C3，判断 router 是否适合做统一入口。
4. 最后再考虑 Codex 专用 adapter、metadata、streaming 或 responses 细节优化。

## 目前不做什么

- 不把 `labagent-agent` 强行设为 Codex 默认后端。
- 不为了 Codex 兼容立刻实现完整 Agent Runtime。
- 不把 RAG 接进每一次编码请求。
- 不为了通过一个客户端测试去隐藏真实错误。
