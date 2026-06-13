# Contributing to agent-input-gate

Thanks for your interest in contributing! This project gates agent inputs with
composable validation rules and aims to stay small, dependency-free, and easy to
reason about. The guidelines below keep contributions consistent with the
existing codebase and CI.

## Getting started

This project targets **Python 3.10+** and has zero runtime dependencies.

1. Fork and clone the repository.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # On Windows: .venv\Scripts\activate
   ```

3. Install the package in editable mode with the development extras:

   ```bash
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   ```

## Development workflow

1. Create a topic branch off `main`:

   ```bash
   git checkout -b your-feature-name
   ```

2. Make your change. Keep the public API small and additive where possible.
3. Add or update tests under `tests/` for any behavior change.
4. Run the checks locally before opening a pull request (see below).

## Running checks

CI runs the same two checks on Python 3.10 through 3.13, so please run them
locally first:

```bash
# Lint
ruff check src/ tests/

# Tests
pytest -v --tb=short
```

Both commands should pass cleanly. If `ruff` reports fixable issues, you can
apply automatic fixes with `ruff check --fix src/ tests/` and review the result.

## Pull requests

- Keep each pull request focused on a single change.
- Describe the motivation and summarize the change in the PR description.
- Ensure lint and tests pass; the CI workflow in `.github/workflows/ci.yml`
  must be green before a PR can be merged.
- Update the README or docstrings if you change user-facing behavior.

## Coding conventions

- Prefer clear, explicit code over cleverness.
- Avoid adding third-party runtime dependencies; a core goal of this project is
  to remain dependency-free.
- Follow the style enforced by `ruff`.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE) that covers this project.
