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
