# Configuration Guidance

## What is it?

Configuration in the context of the ``rap-toolkit`` package refers to a separate file that contains all information relevant to running the pipeline. This can include specific file locations, variables, and other metadata surrounding the package. 

## Types of configuration

``rap-toolkit`` has three levels of configuration. 

### Pipeline Configuration 

**Pipeline Configuration** refers to information required to run the ``Pipeline``. This information is read from the config file into a ``PipelineConfig`` instance to be used throughout the ``Pipeline``. It is a crucial step to setting up a ``Pipeline`` and without it, the ``Pipeline`` will not be able to function. 

**Structure**

Full documentation on the ``PipelineConfig`` class is available within the docstrings however a basic outline of the components that can go into the ``PipelineConfig`` are below. All items required have inbuilt defaults so if you do not want to set each instance, the ``Pipeline`` will create a default one itself.

```yaml
pipeline_variables:
    name: The name of your pipeline
    backend: The code language that you use to run the Pipeline (currently only supports python)
    stages: List all stages in your Pipeline and the associated information
        stage_1:
            name: The name of your stage
            location: The location of your stage
            dependencies: [] Any stages that need to be run before this stage
        stage_2:
            name: The name of your stage
            location: The location of your stage
            dependencies: [] Any stages that need to be run before this stage 
    working_dir: The directory that the pipeline is being run through
    project_root: The top level directory where all the information is stored
    data_dir: The directory where the data is stored
    output_dir: The directory where outputs will go
    log_dir: The directory where the pipeline log will go
    overwrite: Boolean whether to allow overwriting of data/outputs
    metadata: {{}} Any additional information you'd like to store about the pipeline
    stages_to_run:
        stage_1: Boolean whether to run stage
        stage_2: Boolean whether to run stage
```
### Stage Configuration 

**Stage configuration** refers to any variable names or pieces of information that are required to be fed into a single ``Stage``. ``Pipeline`` instances will still run if there are no ``Stage`` configurations however this is useful to be a single point of updating rather than manually udating every reference within the script. 

In the below example, the variables are attached to keys without meaningful names however it is advisable to use meaningful names. Examples: *"sex":"sex_at_birth"* or *"reference_period_start":"start_date"*

```yaml
stage_configuration:
    stage_1: 
        var_1: Input the name of the variable you'd like to insert into your code
        var_2: Input the name of the variable you'd like to insert into your code
    stage_2: 
        var_1: Input the name of the variable you'd like to insert into your code
```

### Global Configuration

**Global configuration** refers to any variable names or piece of information that are required for multiple ``Stage`` scripts. These variables do not have to be called in *all* scripts but instead provides a single point of edit rather than needing to update multiple ``Stage`` configurations. 

These should be populated with the same key: value naming as ``Stage`` configurations to ease readability.

```yaml
global_configuration: 
    var_1: Input the name of the variable you'd like to insert into your code
    var_2: Input the name of the variable you'd like to insert into your code 
```

## How to write a configuration file

A configuration file should be in the **same directory** as your main.py file however can realistically be stored anywhere provided you accurately define the path to it. 

It should be a **single .yaml file** that contains all three types of configuration. Even if you do not require one type of configuration, it is recommended to put the heading in but leave it blank. A full example can be seen in the example pipeline_2 code. 

```shell
.
├── onsrap/                     
├── examples/                   
│   ├── pipeline_2/             
│   │   ├── data/
│   │   ├── outputs/
│   │   ├── scripts/
│   │   ├── conf.yaml       # Example Configuration File
│   │   └── main.py
│   └──

```

A *minimum* configuration file should look like below.
```yaml
pipeline_configuration:

stage_configuration:

global_configuration: 
```

There are a list of aliases that can be used for configuration keys other than the 3 listed in the minimum example. These are:
- pipepline_configuration, pipeline_variables, pipeline_config
- stage_configuration, stage_config
- global_configuration, global_config, global_variables, global_vars

You **must** use one of these aliases otherwise the configuration will not be detected.

## How to use a configuration file
Once the file is written, how do you use it to create a ``Pipeline``? 

An example is seen in the example pipeline_2 ``main.py`` file:
```shell
.
├── onsrap/                     
├── examples/                   
│   ├── pipeline_2/             
│   │   ├── data/
│   │   ├── outputs/
│   │   ├── scripts/
│   │   ├── conf.yaml       
│   │   └── main.py         # Example configuration utilisation
│   └──

```

however the basic code works as below: 
```python
config_file_path = "file/path/location/for/config.yaml"

pipeline = Pipeline.from_config(config_file_path)
```

From this point, the ``Pipeline`` instance functions as normal. 
