# Draft Testing Guide

## What this guide covers

This guide explains how to run the test suite and what to check before opening a pull request.

## Prerequisites

Before running tests, install the development dependencies:

```shell
python -m pip install -U pip setuptools
pip install -e .[dev]
```

If you plan to use pre-commit hooks, also run:

```shell
pre-commit install
```

## Run the tests

From the repository root, run the full test suite with:

```shell
pytest
```

To run a specific test file, use:

```shell
pytest tests/test_pipeline.py
```

To run a single test class or function, use standard pytest selection syntax.

## What to check before review

Before you ask for review, confirm that:

- the test suite passes
- new behavior is covered by tests where practical
- documentation updates match the code changes
- any warnings or failures are understood and intentional

## Suggested validation workflow

A practical local workflow is:

1. install the dev dependencies
2. run the relevant tests for the area you changed
3. run the full suite before submitting a PR
4. check formatting and linting if your change affects code

## Notes for contributors

This project keeps tests in the top-level `tests/` directory. Test file names should begin with `test_` so pytest can discover them.

If a change affects pipeline behavior, it is usually worth checking:

- pipeline construction
- stage execution
- logging or run directory behavior
- configuration parsing

