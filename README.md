# `onsrap`

[![Lint](https://github.com/ONSdigital/onsrap/actions/workflows/ci-lint.yml/badge.svg?branch=main)](https://github.com/ONSdigital/onsrap/actions/workflows/ci-lint.yml)
[![Security](https://github.com/ONSdigital/onsrap/actions/workflows/ci-security.yml/badge.svg?branch=main)](https://github.com/ONSdigital/onsrap/actions/workflows/ci-security.yml)
[![Type Check](https://github.com/ONSdigital/onsrap/actions/workflows/ci-typecheck.yml/badge.svg?branch=main)](https://github.com/ONSdigital/onsrap/actions/workflows/ci-typecheck.yml)
[![Tests](https://github.com/ONSdigital/onsrap/actions/workflows/ci-tests.yml/badge.svg?branch=main)](https://github.com/ONSdigital/onsrap/actions/workflows/ci-tests.yml)
[![Build](https://github.com/ONSdigital/onsrap/actions/workflows/ci-build.yml/badge.svg?branch=main)](https://github.com/ONSdigital/onsrap/actions/workflows/ci-build.yml)
[![Coverage](https://codecov.io/gh/ONSdigital/onsrap/branch/main/graph/badge.svg)](https://codecov.io/gh/ONSdigital/onsrap)

A simple Pipeline orchestration package.

```{warning}
Where this documentation refers to the root folder we mean where this README.md is
located.
```
## What is `onsrap`?

Reproducible Analytical Pipelines (RAPs) are a cornerstone of high quality statistics. Reproducible refers to the concept that if code is run multiple times with the same inputs, it will produce the same outputs. A pipeline is a series of stages (small chunks of work) which are run in a specified order to produce desired outputs. Pipelines are crucial to reproducible work as they ensure that the code is run consistently. This increases the quality of the outputs by ensuring as little manual input as possible. 

ONSRap is a Python package that automatically orchestrates and runs these RAPs. The goal is to standardise how pipelines are run to reduce developer time required to convert existing code into RAP standards. As well as reducing developer time, this package also supports achieving RAP standards through items 4, 6, and 10. These are accomplished through this package by: 

 - Item 4: Document everything that is needed to write and run the code
    - This package includes inbuilt logging that records when the pipeline was run as well as the Pipeline configuration used. 

- Item 6: Code modules should run end-to-end without manual intervention
    - This package is designed whereby once the configuration has been provided by the user and the main.py file is run, no further human input is required. 

- Item 10: Don't reinvent the wheel
    - Multiple pipelines exist within the ONS and each have the potential to be orchestrated in different ways. This package aims to standardise the orchestration, ensuring consistency across pipelines. This consistency means that developers are more easily able to move between pipelines as they will all be structured in a similar way.  

For more information on the ONS Rap Minimum Standards, please see the full [standards documentation][standards].

## Getting started

To start using this project, first make sure your system meets its
requirements.

It's suggested that you install this package and its requirements within
a virtual environment.

Stages should use a functional style. A ``stage`` can be a file or a callable item, such as a function. File stages should define an entrypoint function that runs the stage; files without an entrypoint can use subprocess fallback, but the package has less control over that execution mode.

There should be a parent file that sets out configuration, required directories and file paths, and builds the ``Pipeline`` instance. It is recommended that this is named something similar to ``main.py`` so that it is easy for users to see where the ``Pipeline`` starts. This file will be what is run through the terminal to run the entire pipeline.    

## Requirements

- Python 3.14.6 installed

Contributors have some additional requirements - please see our [contributing guidance][contributing].

## Installing the package

Whilst in the root folder, in a terminal, you can install the package and its
Python dependencies using:

```shell
python -m pip install -U pip setuptools
pip install -e .
```

### Install for contributors (Python only)

To install the contributing requirements, use:
```shell
python -m pip install -U pip setuptools
pip install -e .[dev]
pre-commit install
```

This installs an editable version of the package. This means that when you update the
package code you do not have to reinstall it for the changes to take effect.
This saves a lot of time when you test your code.

Remember to update the setup and requirement files inline with any changes to your
package.

## Running the pipeline (Python only)
### Running Your Own Pipeline
To run your own Pipeline, you will need to build a ``Pipeline`` instance. This can be built using the from_files() method which requires a list of strings or Paths for your individual ``stages``. These are then compiled into a ``Pipeline`` instance. A ``Pipeline`` instance can also be created using the from_dict() method which takes a dictionary containing each attribute of the intented ``Pipeline`` instance and converts it.

You will also need to define your ``PipelineConfig`` instance. This contains information regarding the working directory, project root, data directory, and log directory required to run the ``Pipeline`` as well as any metadata that you feel needs to be logged. 

Lastly, you need to define any ``dependencies`` required for the ``stages``. These are whether any stage needs to be run before another stage. These should be structured as a dictionary with the name of the stage as the key and the value is the stage/s that need to run before it as a tuple. 

Both ``PipelineConfig`` and ``dependencies`` should be parsed into the ``Pipeline`` instance. 

Once you have your ``Pipeline`` instance, you can run the ``Pipeline.run()`` method which will run the entire ``Pipeline`` instance that has been created.

### Example Pipeline
The main runnable example now lives in `examples/pipeline_1/main.py`.
It builds a three-stage pipeline from numbered scripts under `examples/pipeline_1/scripts/`.
To run the example, use:

```shell
python examples/pipeline_1/main.py
```

Alternatively, most Python IDEs allow you to run the code directly using a `run` button.

## Required secrets and credentials

No secrets or credentials are required for running this package.


## Project structure layout

The ONSRap repository has the following structure:

```shell
.
├── onsrap/
│   ├── data/
│   │   ├── raw/
│   │   ├── interim/
│   │   └── processed/
│   ├── onsrap/
│   │   ├── example_modules/
│   │   │   ├── __init__.py
│   │   │   └── example_module.py
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   ├── execution.py
│   │   ├── graph.py
│   │   ├── loader.py
│   │   ├── models.py
│   │   ├── pipeline.py
│   │   ├── run_pipeline.py
│   │   ├── runner.py
│   │   └── stage.py
│   ├── examples/
│   │   ├── pipeline_1/
│   │   │   ├── data/
│   │   │   │   └── orders.csv
│   │   │   ├── logs/
│   │   │   │   └── onsrap.log
│   │   │   ├── runs/
│   │   │   │   └── README.md
│   │   │   └── scripts/
│   │   │   │   ├── 0_data_validation.py
│   │   │   │   ├── 1_preprocessing.py
│   │   │   │   └── 2_reporting.py
│   │   │   ├── Example.md
│   │   │   └── main.py
│   │   ├── pipeline_2/
│   │   └── pipeline_3/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── repo_tests_README.md
│   │   ├── test_execution.py
│   │   ├── test_models.py
│   │   ├── test_pipeline_architecture.py
│   │   ├── test_pipeline.py
│   │   └── test_stage.py
│   └──
└── 
```

## Licence

Unless stated otherwise, the codebase is released under the MIT License. This covers
both the codebase and any sample code in the documentation. The documentation is ©
Crown copyright and available under the terms of the Open Government 3.0 licence.

## Contributing

If you want to help us build and improve `onsrap`, please take a look at our
[contributing guidelines][contributing].

## Acknowledgements

This project structure is based on the [`govcookiecutter` template project][govcookiecutter].

[contributing]: https://github.com/best-practice-and-impact/govcookiecutter/blob/main/%7B%7B%20cookiecutter.repo_name%20%7D%7D/docs/contributor_guide/CONTRIBUTING.md
[govcookiecutter]: https://github.com/best-practice-and-impact/govcookiecutter
[docs-loading-environment-variables]: https://github.com/best-practice-and-impact/govcookiecutter/blob/main/%7B%7B%20cookiecutter.repo_name%20%7D%7D/docs/user_guide/loading_environment_variables.md
[docs-loading-environment-variables-secrets]: https://github.com/best-practice-and-impact/govcookiecutter/blob/main/%7B%7B%20cookiecutter.repo_name%20%7D%7D/docs/user_guide/loading_environment_variables.md#storing-secrets-and-credentials
[standards]: https://best-practice-and-impact.github.io/ONS_minimum_RAP/