Quickstart Guide

## What this guide covers

This guide shows the shortest path from a fresh clone to a first pipeline run.

## Requirements

Before you begin, make sure you have:

- Python 3.10 or later
- A virtual environment
- The package installed in editable mode
- One or more pipeline stage files

## Install the package

From the repository root, install the package and its runtime dependencies:

```shell
python -m pip install -U pip setuptools
pip install -e .
```

If you are contributing to the project, install the development extras instead:

```shell
python -m pip install -U pip setuptools
pip install -e .[dev]
pre-commit install
```

## Create a minimal pipeline

A pipeline needs at least one stage. A simple structure is:

- a `main.py` file that creates the pipeline
- one or more stage scripts
- a configuration object or YAML file, depending on how you want to run it

A minimal pipeline can be created from a list of stage files:

```python
from pathlib import Path
from rap_toolkit import Pipeline

stages = [Path("examples/pipeline_1/scripts/0_data_validation.py")]
pipeline = Pipeline.from_files(stages)
pipeline.run()
```

## Run from a config file

If you prefer configuration-driven execution, create a YAML file and load it into the pipeline:

```python
from pathlib import Path
from rap_toolkit import Pipeline

config_path = Path("examples/pipeline_2/conf.yaml")
pipeline = Pipeline.from_config(config_path)
pipeline.run()
```

## Where outputs go

`rap-toolkit` creates run-specific output locations so repeated runs do not overwrite each other. Stage code should use the execution context helpers provided by the package rather than hard-coding output paths.

Useful helpers include:

- `get_data_dir()` for reading input data
- `resolve_output_root()` for writing run outputs
- `resolve_given_path()` for reusing paths from earlier stages

## Caveats

This method will use default values for **PipelineConfig**. Please review the defaults below to ensure these are appropriate for you, otherwise you will need to create and define your own PipelineConfig.

```shell
name: None
stages_to_run: None
backend: str = "python"
work_dir: FileSystemSetUp()
project_root: None
output_dir: None
log_dir: FileSystemSetUp(workspace_path="logs")
data_dir: FileSystemSetUp(workspace_path="data")
allow_subprocess_fallback: True
python_executable: None
metadata: {}
overwrite: False
ssl_file: None
```

## Example project layout

A typical project has:

- a `main.py` entry point
- a `scripts/` directory for stages
- a `data/` directory for inputs
- a `runs/` or `outputs/` directory for generated files

