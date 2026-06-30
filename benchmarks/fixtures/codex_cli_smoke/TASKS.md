# Codex CLI Manual Tasks

Run these one at a time in a temporary copy of this directory.

## C1 - Read

Ask Codex:

```text
Read this project and tell me what each file does. Do not edit files.
```

Expected:

- It reads `README.md`, `app.py`, and `tests/test_app.py`.
- It does not modify files.

## C2 - Create File

Ask Codex:

```text
Create notes.md with one sentence explaining this fixture.
```

Expected:

- `notes.md` exists.
- The content is about Codex CLI / LabAgent compatibility smoke testing.

## C3 - Single File Edit

Ask Codex:

```text
Add clear docstrings to add and format_total in app.py, then run the tests.
```

Expected:

- It updates `app.py`.
- It does not change behavior.
- `python -m unittest discover -s tests -p "test_*.py"` passes.

## C4 - Multi-file Edit

Ask Codex:

```text
Update app.py and tests/test_app.py so format_total returns "total=<sum>; count=<count>". Run the tests and fix any failure.
```

Expected:

- It changes both `app.py` and `tests/test_app.py`.
- `python -m unittest discover -s tests -p "test_*.py"` passes.

## C5 - Add Function With Tests

Ask Codex:

```text
Add a mean_value(items: list[int]) -> float function. It should raise ValueError for an empty list. Add unit tests and run them.
```

Expected:

- `mean_value` is added.
- Tests cover normal and empty-list cases.
- Unit tests pass.

## C6 - Failure Recovery

Before asking Codex, intentionally break `format_total` by returning the wrong string. Then ask:

```text
Run the tests, identify the failure, and fix the implementation without changing the test intent.
```

Expected:

- It runs tests.
- It identifies the failing assertion.
- It fixes `app.py`.
- Tests pass.

## C7 - Longer Context Edit

Ask Codex:

```text
Read README.md, TASKS.md, app.py, and tests/test_app.py. Then add a describe_fixture() -> str helper in app.py, add unit tests for it, run the tests, and keep your final answer concise.
```

Expected:

- It reads project docs plus code/tests before editing.
- It adds `describe_fixture() -> str`.
- It adds a unit test for `describe_fixture`.
- It does not remove existing functions or tests.
- `python -m unittest discover -s tests -p "test_*.py"` passes.

## C8 - Backend Error Experience

This task is not about editing files. It checks whether Codex shows understandable errors when the backend is unavailable or misconfigured.

Run these as short tests, one at a time, and restore the correct config after each test.

### C8a - Wrong API Key

Temporarily set Codex's LabAgent key to an obviously wrong value, then ask Codex:

```text
Reply with exactly pong.
```

Expected:

- The request fails.
- The error should clearly suggest auth / unauthorized / invalid key.
- Restore the correct key before continuing.

### C8b - Model Or Tunnel Down

Only run this when it is safe to briefly break the route. Stop the 5090 `:12340` tunnel or unload `qwen-agent`, then ask Codex:

```text
Reply with exactly pong.
```

Expected:

- The request fails.
- The error should make it reasonably clear that the backend model or route is unavailable.
- Restart the tunnel / reload the model before continuing.

## C9 - labagent-agent Backend Smoke

Switch Codex config from the LiteLLM main gateway to the Agent Router:

```text
Base URL: http://82.156.69.153:18020/v1
Model: labagent-agent
Key: <LABAGENT_AGENT_API_KEY>
wire_api: responses
```

Then run C0-C3 only:

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

Expected:

- C0-C3 work through `labagent-agent`.
- If any fail, record whether the failure is auth, streaming/responses compatibility, router behavior, or model output quality.
- Do not promote `labagent-agent` to the default Codex backend unless this is at least as stable as `qwen-agent`.
