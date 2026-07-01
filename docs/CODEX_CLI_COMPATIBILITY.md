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
| fixture C1-C6 | 已通过 | 能读项目、创建文件、单文件编辑、多文件编辑、添加函数+测试、根据失败测试修复实现 |

当前仍未认证：

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
| C4 | 多文件修改 | 同时修改 `app.py` 和 `tests/test_app.py`，测试通过 | 已通过 |
| C5 | 运行测试 | 主动执行 `python -m unittest discover` 并解释结果 | 已通过 |
| C6 | 失败修复 | 先看到失败测试，再定位并修复 | 已通过 |
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

## 2026-06-30 David C1-C6 结果

后端：

```text
Base URL: http://82.156.69.153:8000/v1
Model: qwen-agent
wire_api: responses
```

结果摘要：

| ID | 结果 | 观察 |
|----|------|------|
| C1 | 通过 | 能读取 `README.md`、`app.py`、`tests/test_app.py`、`TASKS.md` 并说明文件用途；未修改文件。 |
| C2 | 通过 | 创建 `notes.md`，内容符合 smoke fixture 说明。 |
| C3 | 通过 | 给 `app.py` 两个函数添加 docstring，不改变行为；最终用 `unittest` 跑通。 |
| C4 | 通过 | 同时修改 `app.py` 和 `tests/test_app.py`，把 `format_total` 改为返回 `total=<sum>; count=<count>`，测试通过。 |
| C5 | 通过 | 添加 `mean_value(items: list[int]) -> float`，为空列表抛 `ValueError`，补测试并验证。 |
| C6 | 通过 | 在 `format_total` 被故意改坏后，能运行测试、定位失败并修复实现；最终 `unittest` 通过。 |

可接受瑕疵：

- 第一次尝试在 PowerShell 使用 `&&`，报错后改用 `;`。
- 曾尝试 `pytest`，David 环境没有安装后改用标准库 `unittest`。
- 直接运行 `python tests/test_app.py` 会遇到导入路径问题；正确方式是从项目根目录运行 `python -m unittest discover -s tests -p "test_*.py"` 或 `python -m unittest tests.test_app`。

结论：`Codex CLI + LabAgent + qwen-agent` 已通过小型真实开发 workflow smoke，覆盖读项目、创建文件、单文件修改、多文件修改、运行测试和失败修复。还不能宣称完整团队生产可用，因为 C7 长上下文、C8 后端异常和 C9 `labagent-agent` 后端仍未测。

## 推荐推进顺序

1. 先跑 C7，确认稍长上下文下仍能读懂 fixture 文档、代码和测试。
2. 再测试 C8，确认 wrong key / tunnel down / model unloaded 的错误体验可接受。
3. 然后用 `labagent-agent` 跑 C0-C3，判断 router 是否适合做统一入口。
4. 最后再考虑 Codex 专用 adapter、metadata、streaming 或 responses 细节优化。

## C7-C9 执行顺序

每个正常编辑任务都建议先重置一份干净 fixture：

```powershell
$Repo = "F:\CodexTest\AI_Lab_Platform"
$Run = "F:\CodexTest\codex_cli_smoke_run"

cd F:\CodexTest
if (Test-Path $Run) { Remove-Item -Recurse -Force $Run }
Copy-Item -Recurse "$Repo\benchmarks\fixtures\codex_cli_smoke" $Run
cd $Run
python -m unittest discover -s tests -p "test_*.py"
codex
```

### C7：长一点的上下文任务

在 `qwen-agent` 默认后端下粘贴：

```text
Read README.md, TASKS.md, app.py, and tests/test_app.py. Then add a describe_fixture() -> str helper in app.py, add unit tests for it, run the tests, and keep your final answer concise.
```

通过后记录：

- 是否读了 README / TASKS / app / tests。
- 是否同时改了 `app.py` 和 `tests/test_app.py`。
- 是否保留原有 `add` / `format_total` 测试。
- `python -m unittest discover -s tests -p "test_*.py"` 是否通过。

### C8：错误体验

C8 不需要 fixture 干净目录，它测试的是后端失败时 Codex 的报错是否清楚。

先测 wrong key：

1. 把 David 的 Codex LabAgent key 临时改成明显错误值。
2. 启动 Codex，粘贴：

```text
Reply with exactly pong.
```

3. 记录错误是否像 auth / unauthorized / invalid key。
4. 立刻恢复正确 key。

再测模型或隧道不可用：

1. 只在安全时间窗口短暂停掉 5090 `:12340` 隧道，或者卸载 `qwen-agent`。
2. 启动 Codex，粘贴：

```text
Reply with exactly pong.
```

3. 记录错误是否能看出 backend / route / model unavailable。
4. 立刻恢复隧道或重新 load 模型。

### C9：`labagent-agent` 后端

把 Codex provider 临时切到：

```text
Base URL: http://82.156.69.153:18020/v1
Model: labagent-agent
Key: <LABAGENT_AGENT_API_KEY>
wire_api: responses
```

只跑 C0-C3：

```text
Reply with exactly pong.
```

```text
Read this project and tell me what each file does. Do not edit files.
```

```text
Create notes.md with one sentence explaining this fixture.
```

```text
Add clear docstrings to add and format_total in app.py, then run the tests.
```

判断标准：

- 如果 C0-C3 稳定，`labagent-agent` 可以继续作为 Codex 实验入口。
- 如果失败，记录失败类型，不要把它设为团队默认后端。
- 团队默认后端仍是 `qwen-agent` 直连 LiteLLM。

2026-07-01 首轮 C9 观察：

- David 机器直接调用公网 `/health` 返回 `ok=true`。
- David 机器直接调用公网 `/v1/chat/completions` 可返回 `labagent.route=direct_chat`、`final_model=qwen-agent`。
- Codex CLI 接入 `labagent-agent` 时失败：`stream disconnected before completion: stream closed before response.completed`。
- 判断：链路和模型可用，失败点在 Codex 使用的 `/v1/responses stream=true` 协议兼容层。旧 router 没有发送 Responses API SSE 的 `response.completed` 事件。
- 当前代码已补 `/v1/responses stream=true` 的 SSE 降级事件；重启 5090 上的 `services.agent.server` 后再复测 C9。

## 目前不做什么

- 不把 `labagent-agent` 强行设为 Codex 默认后端。
- 不为了 Codex 兼容立刻实现完整 Agent Runtime。
- 不把 RAG 接进每一次编码请求。
- 不为了通过一个客户端测试去隐藏真实错误。
