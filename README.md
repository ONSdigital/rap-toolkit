# `rap-toolkit`

A simple Pipeline orchestration package.

```{warning}
Where this documentation refers to the root folder we mean where this README.md is
located.
```
## What is `rap-toolkit`?

Reproducible Analytical Pipelines (RAPs) are a cornerstone of high quality statistics. Reproducible refers to the concept that if code is run multiple times with the same inputs, it will produce the same outputs. A pipeline is a series of stages (small chunks of work) which are run in a specified order to produce desired outputs. Pipelines are crucial to reproducible work as they ensure that the code is run consistently. This increases the quality of the outputs by ensuring as little manual input as possible. 

``rap-toolkit`` is a Python package that automatically orchestrates and runs these RAPs. The goal is to standardise how pipelines are run to reduce developer time required to convert existing code into RAP standards. As well as reducing developer time, this package also supports achieving RAP standards through items 4, 6, and 10. These are accomplished through this package by: 

 - Item 4: Document everything that is needed to write and run the code
    - This package includes inbuilt logging that records when the pipeline was run as well as the Pipeline configuration used. 

- Item 6: Code modules should run end-to-end without manual intervention
    - This package is designed whereby once the configuration has been provided by the user and the main.py file is run, no further human input is required. 

- Item 10: Don't reinvent the wheel
    - Multiple pipelines exist within the ONS and each have the potential to be orchestrated in different ways. This package aims to standardise the orchestration, ensuring consistency across pipelines. This consistency means that developers are more easily able to move between pipelines as they will all be structured in a similar way.  

For more information on the ONS RAP Minimum Standards, please see the full [standards documentation][standards].

## Getting started

To start using this project, first make sure your system meets its
requirements.

It's suggested that you install this package and its requirements within
a virtual environment.

Stages should use a functional style. A ``stage`` can be a file or a callable item, such as a function. File stages should define an entrypoint function that runs the stage; files without an entrypoint can use subprocess fallback, but the package has less control over that execution mode.

There should be a parent file that sets out configuration, required directories and file paths, and builds the ``Pipeline`` instance. It is recommended that this is named something similar to ``main.py`` so that it is easy for users to see where the ``Pipeline`` starts. This file will be what is run through the terminal to run the entire pipeline.    

## Requirements

- Python 3.10 installed

Contributors have some additional requirements - please see our [contributing guidance][contributing].

## Dependencies / System Requirements
- Windows Operating System
- Local File System (support for remote/cloud computing in development)

## Installing the package

Whilst in the root folder, in a terminal, you can install the package and its
Python dependencies using:

```shell
python -m pip install -U pip setuptools
pip install -e .
```

The package is not currently available on PyPI however this is a route for future development. 

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
### Quick Start Code Example
There are 3 ways to create and run a ``Pipeline``. Whilst you can create a ``Pipeline`` that has entirely default None values, this will not run anything substantial. You will require:
- at least **1** stage (callable or from_file)

**Pipeline.from_files()** 
A ``Pipeline`` is created from stage files provided.
```python
from rap-toolkit import Pipeline
scripts = [
    "location/of/script_1.py",
    Path(location/of/script_2.py)
]

pipeline = Pipeline.from_files(scripts)
pipeline.run()
```

**Pipeline.from_config()** 
A ``Pipeline`` is created from a configuration. This configuration can be blank and default values will be populated.
```python
from rap-toolkit import Pipeline

#Config can either be a file path
config = Path(full/location/of/config.yaml) or "full/location/of/config.yaml"

#or a dictionary
config = {}

pipeline = Pipeline.from_config(config)
pipeline.run()
```

**Direct Calling Pipeline()**
Calling Pipeline() directly will create a default Pipeline instance with no stages, configuration, or any details. This in itself will fail if you run Pipeline.run() however you can add stages individually using the add_stage() method. 
```python
Pipeline(name = None,
        backend = "python",
        config = None,
        stages = None,
        dependencies = None,
        logger = None,
        executor = None)
```

The following optional extension ensures that run outputs are stored in run specific directories, preventing overwriting of outputs. This should be used when you are determining your file output locations in the ``main()`` function of your scripts.  
```python


```


### Running Your Own Pipeline
To run your own Pipeline, you will need to build a ``Pipeline`` instance. This can be built using the from_files() method which requires a list of strings or Paths for your individual ``stages``. These are then compiled into a ``Pipeline`` instance. A ``Pipeline`` instance can also be created using the from_dict() method which takes a dictionary containing each attribute of the intented ``Pipeline`` instance and converts it.

You will also need to define your ``PipelineConfig`` instance. This contains information regarding the working directory, project root, data directory, and log directory required to run the ``Pipeline`` as well as any metadata that you feel needs to be logged. 

Lastly, you need to define any ``dependencies`` required for the ``stages``. These are whether any stage needs to be run before another stage. These should be structured as a dictionary with the name of the stage as the key and the value is the stage/s that need to run before it as a tuple. 

Both ``PipelineConfig`` and ``dependencies`` should be parsed into the ``Pipeline`` instance. 

Once you have your ``Pipeline`` instance, you can run the ``Pipeline.run()`` method which will run the entire ``Pipeline`` instance that has been created.

All runs of the ``Pipeline`` will be stored in a ``run_directory`` that is unique. This will prevent any overwriting of previous runs' outputs. In order for this to work properly, data locations in the ``main.py`` file need to be calculated using specific functions within the package. An example of this can be seen in the Quick Start Code Example section. 

There is also utility to use a configuration file to store all information required to run the ``Pipeline``. Information on how to set up the configuration file can be found in our [configuration guidance][configuration_guidance]. 

### Example Pipeline
There are 2 example pipelines which live in `examples/pipeline_1/main.py` and `examples/pipeline_2/main.py`.
Both build a three-stage pipeline from numbered scripts under `../scripts/`.

``Pipeline_1`` utilises a function within the ``main.py`` script that builds all the required information before returning a ``Pipeline`` instance using the ``from_files()`` method. This is built in an idea fashion however is not always practical for research code. 

``Pipeline_2`` utilises a configuration file in `examples/pipeline_2/conf.yaml` rather than building the ``Pipeline`` instance through attributes within the main.py script. This pipeline is designed to be more rough-and-ready to show how the package can be used even on a work-in-progress system. 

To run the examples, use:

```shell
python examples/pipeline_1/main.py
```

or

```shell
python examples/pipeline_2/main.py
```

Alternatively, most Python IDEs allow you to run the code directly using a `run` button.

## Required secrets and credentials

No secrets or credentials are required for running this package.

## Troubleshooting
TO BE POPULATED


## Project structure layout

The ``rap-toolkit`` repository has the following structure:

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
│   │   ├── py.typed
│   │   ├── run_pipeline.py
│   │   ├── runner.py
│   │   ├── stage.py
│   │   └── warnings.py
│   ├── examples/
│   │   ├── pipeline_1/
│   │   │   ├── data/
│   │   │   │   └── orders.csv
│   │   │   ├── runs/
│   │   │   │   └── README.md
│   │   │   └── scripts/
│   │   │   │   ├── 0_data_validation.py
│   │   │   │   ├── 1_preprocessing.py
│   │   │   │   └── 2_reporting.py
│   │   │   ├── Example.md
│   │   │   ├── main.py
│   │   │   └── main2.py
│   │   ├── pipeline_2/
│   │   │   ├── data/
│   │   │   │   ├── orders_cleaned.csv
│   │   │   │   ├── orders_prepped.csv
│   │   │   │   └── orders.csv
│   │   │   ├── outputs/
│   │   │   │   ├── runs/
│   │   │   │   └── order_analysis.md
│   │   │   └── scripts/
│   │   │   │   ├── 0_clean_data.py
│   │   │   │   ├── 1_derive_vars.py
│   │   │   │   └── 2_reporting.py
│   │   │   ├── conf.yaml
│   │   │   ├── Example.md
│   │   │   └── main.py
│   │   └── pipeline_3/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── repo_tests_README.md
│   │   ├── test_execution.py
│   │   ├── test_loader.py
│   │   ├── test_logger.py
│   │   ├── test_models.py
│   │   ├── test_pipeline_architecture.py
│   │   ├── test_pipeline.py
│   │   ├── test_runner.py
│   │   └── test_stage.py
│   ├── .env
│   ├── .envrc
│   ├── .gitignore
│   ├── .pre-commit-config.yaml
│   ├── .secrets.baseline
│   ├── CHANGELOG.md
│   ├── cliff.toml
│   ├── CODE_OF_CONDUCT.md
│   ├── configuration.md
│   ├── conftest.py
│   ├── CONTRIBUTING.md
│   ├── DESIGN.md
│   ├── LICENSE
│   ├── make.bat
│   ├── Makefile
│   ├── pyproject.toml
│   ├── README.md
│   ├── setup.cfg
│   └── setup.py
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

[contributing]: docs\contributor_guide\CONTRIBUTING.md
[govcookiecutter]: https://github.com/best-practice-and-impact/govcookiecutter
[docs-loading-environment-variables]: https://github.com/best-practice-and-impact/govcookiecutter/blob/main/%7B%7B%20cookiecutter.repo_name%20%7D%7D/docs/user_guide/loading_environment_variables.md
[docs-loading-environment-variables-secrets]: https://github.com/best-practice-and-impact/govcookiecutter/blob/main/%7B%7B%20cookiecutter.repo_name%20%7D%7D/docs/user_guide/loading_environment_variables.md#storing-secrets-and-credentials
[standards]: https://best-practice-and-impact.github.io/ONS_minimum_RAP/
[configuration_guidance]: docs\configuration_guidance.md