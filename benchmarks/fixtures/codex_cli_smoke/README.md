# Codex CLI Smoke Fixture

This tiny project is used to manually verify whether Codex CLI can use LabAgent as a coding backend.

It is intentionally small:

- `app.py` contains simple pure functions.
- `tests/test_app.py` contains deterministic unit tests.
- `TASKS.md` contains manual tasks for Codex CLI.

Run tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Use a temporary copy when testing Codex CLI so the fixture stays clean.
