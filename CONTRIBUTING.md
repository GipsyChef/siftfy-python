# Contributing to siftfy-python

Thanks for helping improve the Siftfy Python SDK. This repository is a small,
typed Python client for the Siftfy spam-classification API, so changes should
stay focused on SDK behavior, packaging, tests, or public documentation.

## Development Setup

Use Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Run the same checks that CI runs before opening a pull request:

```bash
ruff check src tests
mypy src
pytest -q
python -m build
```

## Pull Requests

- Keep pull requests focused on one behavior or documentation change.
- Add or update tests for any client behavior change.
- Update README examples or package metadata when user-facing behavior changes.
- Avoid committing generated caches, local virtual environments, credentials, or
  service-specific test data.

## Contributor Certificate

By contributing, you agree that your contribution is licensed under the MIT
License in this repository.
