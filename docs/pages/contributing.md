# Contributing to Kedro Azure ML

Thank you for your interest in contributing to Kedro Azure ML! This document provides guidelines for contributing to the project.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and considerate in all interactions.

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended)
- [just](https://github.com/casey/just) (optional, for task automation)
- Git

### Development Setup

1. Fork the repository on GitHub

2. Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/kedro-azure-ml.git
cd kedro-azure-ml
```

3. Install dependencies:

```bash
uv sync --group dev
```

4. Install pre-commit hooks:

```bash
uv run pre-commit install
```

## Development Workflow

### Making Changes

1. Create a new branch:

```bash
git checkout -b feature/my-feature
```

2. Make your changes

3. Run tests:

=== "just"

    ```bash
    just test
    ```

=== "nox"

    ```bash
    uvx nox -s test
    ```

=== "uv run"

    ```bash
    uv run pytest
    ```

4. Format and fix code:

=== "just"

    ```bash
    just fix
    ```

=== "nox"

    ```bash
    uvx nox -s fix
    ```

=== "uv run"

    ```bash
    uv run ruff format src tests
    uv run ruff check src tests --fix
    uv run ty check src
    ```

5. Commit your changes:

```bash
git add .
git commit -m "feat: add my feature"
```

We follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

### Running Tests

Kedro Azure ML uses pytest with markers to categorize tests:

- **Fast tests**: Unit tests that run quickly
- **Slow tests**: `@pytest.mark.slow`
- **Integration tests**: `@pytest.mark.integration`

#### Test Commands

Run fast tests only:

=== "just"
    ```bash
    just test-fast
    ```
=== "nox"
    ```bash
    uvx nox -s test_fast
    ```
=== "uv run"
    ```bash
    uv run pytest -m "not slow and not integration"
    ```

Run all tests:

=== "just"
    ```bash
    just test
    ```
=== "nox"
    ```bash
    uvx nox -s test
    ```
=== "uv run"
    ```bash
    uv run pytest
    ```

Run tests with coverage:

=== "just"
    ```bash
    just test-cov
    ```
=== "nox"
    ```bash
    uvx nox -s test_coverage
    ```
=== "uv run"
    ```bash
    uv run pytest --cov=kedro_azure_ml --cov-report=html
    ```

#### CI Test Strategy

1. **Fast tests** (`test-fast` job): Runs on 3.11, 3.13
2. **Full test suite** (`test-full` job): All tests on Ubuntu across 3.11-3.13

### Code Quality

=== "just"
    ```bash
    just lint / just fix / just check
    ```
=== "nox"
    ```bash
    uvx nox -s lint / uvx nox -s fix
    ```
=== "uv run"
    ```bash
    uv run ruff check src tests
    uv run ty check src
    uv run ruff format src tests
    uv run ruff check src tests --fix
    ```

### Docstring Standards

NumPy-style docstrings. Coverage tracked by `interrogate`.

### Documentation

=== "just"
    ```bash
    just build / just serve
    ```
=== "nox"
    ```bash
    uvx nox -s build_docs / uvx nox -s serve_docs
    ```
=== "uv run"
    ```bash
    uv run mkdocs build / uv run mkdocs serve
    ```

## Submitting Changes

1. Push your branch to your fork
2. Open a Pull Request against `main`
3. Fill out the PR template
4. Wait for CI checks and review

## Pull Request Guidelines

- PRs should target the `main` branch
- Keep changes focused and atomic
- Include tests for new functionality
- Update documentation as needed
- Use [Conventional Commits](https://www.conventionalcommits.org/) format for PR titles

## Commit Message Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

## Release Process

1. Create and push a version tag (e.g., `v0.2.0`)
2. CI generates a changelog PR via git-cliff
3. Merge the changelog PR → triggers GitHub Release creation
4. Manually approve PyPI deployment in the GitHub environment

## Questions?

- [Open an issue](https://github.com/stateful-y/kedro-azureml/issues/new)
- [Start a discussion](https://github.com/stateful-y/kedro-azureml/discussions)
