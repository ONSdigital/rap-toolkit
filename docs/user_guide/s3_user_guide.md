# S3 User Guide

## What is S3 and why is it different to local storage?

Amazon S3 (S3) stands for Simple Storage Service and is a **cloud-based object storage system** hosted and operated by Amazon Web Services. 

The key difference between S3 and a local file system is that S3 does not have hierarchical storage. This means that within the 'bucket', all files (or *objects*) are stored at the same level. S3 APIs often given an illusion of hierarchical storage as it is more intuitive. This is done based on shared prefixes in the file names. For this reason, operations such as *resolve*, *is_absolute* or *mkdir* that are utilised in this package for pathing interactions are unnecessary. 

There are other key differences in storage such as how to open an object and different ways to write to files. More information can be found out about S3 storage by reviewing Amazon's [documentation][s3_documentation]. 

## How does rap-toolkit account for these changes?

The module **file_system_setup.py** within this package normalises all file system interactions and allows for file systems to differ on an instance by instance level. Rather than file paths being stored as strings, they are broken down into a **FileSystemSetUp** class. This class converts any file paths into URIs (Uniform Resource Identifiers) which can then be used by the **FileSystemFactory** class to determine which file system is relevant for that path. 

Exact methods for determining these file systems can be viewed in the in-line documentation [here][file_system_setup]. 

There are individual classes for each file system. These classes belong to a custom protocol called *FileSystem* which require all methods that are used in the package. 

Redundant methods within S3 file systems still appear in the **S3FileSystem** class however they return a set value that allows the program to continue functioning without making any changes to the path. 

## What does this mean for usage?

The creation and running of a *Pipeline* work in the same way, regardless of file system. The key differences are what information you provide in the configuration file and how you source the output and run directories within the stages. 

### Configuration File

You will need to set any values that interact with the S3 file system to the full path. An example may be: 

```yaml
working_dir: project/location/of_scripts
project_root: project
data_dir: s3a://bucket_name/all_data_has_this_prefix
output_dir: s3a://bucket_name/project_name
log_dir: project/logs
```

From the above example, you can see how the paths all work independently of each other. For exact definitions of all these paths, please see the documentation on *PipelineConfig* in [models.py][models.py].

### Stage Adjustments

Within each of your stages' *main* functions, you should be calling *get_data_dir*, *resolve_output_root*, or *resolve_given_path* to utilise the data directory, output directory, and run control elements of the package. This is where you will find the most change with utilising S3. 

These functions now have a *path_type* argument which needs to be called. It should be set to "path" if it is stored on the local file system or "uri" if it is stored in the cloud. It will then return either a path object or a string containing the full URI. 

The *ExecutionContext* class now has another method called **extract_bucket_and_key**. This enables you to isolate the bucket and the key from the URI as these are often required separate to the full file path for interactions with the file system that you might be doing, such as saving your outputs. 

You should then save the full URI string for the location where you saved the data to the stage_results for that stage. This way, you can utilise the *resolve_given_path* method in your next stage to source the run speciifc version of the output. 

## What cannot be stored on S3

For architecture reasons, some information cannot be stored on S3 and utilised in this package. These are: 
- logging files
- code

### Logging Files

Logging in the context of this package requires ammendments to a file which is not possible in S3. In order to put logging on S3, the package would need to open the file, save into memory, add the new line, and then overwrite the previous file. This is excessive computationally and therefore a decision was made to restrict logging to the local file system. 

For long term storage of the logs, you can add a method into the main.py file for your project which saves the log out to S3 every run if this is something you would like to do. 

### Code Storage

S3 is designed to store data and therefore is not an appropriate method of working on code. Code should be stored in a local file system and version controlled through Git for best practice. 



**Other than the above changes, everything else should function identically to the local file system**


[s3_documentation]: https://docs.aws.amazon.com/s3/
[file_system_setup]: ../../rap_toolkit/file_system_setup.py
[models.py]: ../../rap_toolkit/models.py
