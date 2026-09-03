from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp

from .errors import StageExecutionError
from .execution import ExecutionContext
from .logger import Logger
from .models import (
    PipelineRun,
    PipelineStatus,
    RunManifest,
    StageResult,
    _yaml_safe_encode,
    now,
)

if TYPE_CHECKING:
    from .pipeline import Pipeline


class PipelineRunner:
    """
    Represents the information required to run the Pipeline.

    Parameters
    ----------
    ``logger`` : Logger class type
        Information used to log progress throughout the Pipeline.
    """

    def __init__(self, logger: Logger | None = None):
        self.logger = logger or Logger()

    def __str__(self) -> str:
        """
        String method that returns a human-readable representation of the ``PipelineRunner`` class.

        Returns
        -------
        str
            A string representation of the ``PipelineRunner`` class with its attributes.
        """
        return (
            f"PipelineRunner Instance Attributes\n"
            f"--------------------------\n"
            f"Logger: {self.logger} \n"
        )

    def __repr__(self) -> str:
        """
        Representation method that returns a human readable representation of the ``PipelineRunner`` class.
        This method is structured to be more concise than the ``__str__`` method and is
        intended for debugging purposes.

        Returns
        -------
        str
            A string representation of the ``PipelineRunner`` class with its attributes.
        """
        return f"PipelineRunner(logger={self.logger})"

    def run(self, pipeline: Pipeline) -> PipelineRun:
        """
        Method that runs a ``Pipeline`` instance.

        This method validates the source information, establishes the directories and
        the context to run the pipeline within, sets out the manifest for the run, attempts
        to run the stages in the order outlined by the ``StageGraph`` instance and logs all
        progress alongside relevant statuses. Before each stage executes, the runner binds
        the current stage name onto the ``ExecutionContext`` so ``context.stage_config``
        resolves to the correct stage-specific configuration.

        It returns a PipelineRun instance containing metadata and logging information for the
        specific run of the whole Pipeline.

        Parameters
        ----------
        ``pipeline`` : Pipeline
            A Pipeline instance that this method will run.

        Raises
        ------
        ``StageExecutionError``
            If the stage is unable to be run. Logs will be created to show a failed stage.
        """
        # Initial Pipeline steps - validate, create run ID and any relevant directories.
        pipeline.validate()

        runtime_id = pipeline._create_runtime_id()
        pipeline.id = runtime_id
        # copies the FileSystemSetUp in run_output to a new variable
        run_dir_set_up = FileSystemSetUp.confirm_typing(
            pipeline.run_output, path_type="dir"
        )
        # changes the workspace path within the copied FileSystemSetUp to include the runtime_id
        run_dir_set_up.workspace_path = (
            run_dir_set_up.workspace_path + "/" + str(runtime_id.get_id())
        )
        file_system = FileSystemFactory.create(run_dir_set_up)
        file_system.mkdir(parents=True, exist_ok=True)

        # Initialise the ExecutionContext which will be passed to each stage as it runs. This
        # context will hold the configuration for the pipeline and for each stage.
        started_at = now()
        context = ExecutionContext(
            pipeline_name=pipeline.name,
            run_id=runtime_id.get_id(),
            config=pipeline.config,
            logger=self.logger,
            run_dir=run_dir_set_up,
            started_at=started_at,
            working_directory=pipeline.config.work_dir,
            stage_configs=dict(pipeline.stage_configs),
            global_config=pipeline.global_config,
        )

        # Ensure the stages are in order and create a manifest that explains the run.

        ordered_stages = pipeline.ordered_stages()
        manifest = pipeline._construct_manifest(runtime_id=runtime_id)
        manifest.stages_run = []
        manifest.outputs = {}
        pipeline.manifest = manifest

        _log_config(run_dir_set_up, context, manifest)

        self.logger.event(
            "Pipeline started",
            name=pipeline.name,
            run_id=runtime_id.get_id(),
            stages=[stage.name for stage in ordered_stages],
        )

        # Execution of the stages in the dependency-driven order.
        stage_results: list[StageResult] = []
        try:
            for stage in ordered_stages:
                self.logger.event(
                    "Executing stage", name=stage.name, source=stage.source_label
                )
                context.set_active_stage(stage.name)
                try:
                    result = stage.run(context, pipeline.executor)
                finally:
                    context.set_active_stage(None)
                context.record(result)
                stage_results.append(result)
                manifest.stages_run.append(result.name)
                manifest.outputs[result.name] = result.outputs

        except StageExecutionError as exc:
            # Handle recording of execution errors.
            if exc.result is not None and context.result_for(exc.result.name) is None:
                context.record(exc.result)
                stage_results.append(exc.result)
                manifest.stages_run.append(exc.result.name)
                manifest.outputs[exc.result.name] = exc.result.outputs

            # Log the failure and raise the exception to indicate the pipeline has failed.
            completed_at = now()
            run = PipelineRun(
                manifest=manifest,
                status=PipelineStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                stage_results=stage_results,
                stage_outputs=context.stage_outputs,
            )
            pipeline.manifest = manifest
            pipeline.last_run = run

            # Creates attributes file in the run_directory to log information for later
            # analysis of pipeline runs
            _log_pipeline_attributes(
                pipeline_run=run, run_dir=run_dir_set_up, context=context
            )

            self.logger.event(
                "Pipeline failed",
                name=pipeline.name,
                run_id=runtime_id.get_id(),
                error=str(exc),
            )
            raise

        # If the pipeline has completed successfully, record the completion and return the run information.
        completed_at = now()
        run = PipelineRun(
            manifest=manifest,
            status=PipelineStatus.SUCCEEDED,
            started_at=started_at,
            completed_at=completed_at,
            stage_results=stage_results,
            stage_outputs=context.stage_outputs,
        )
        pipeline.manifest = manifest
        pipeline.last_run = run

        # Creates attributes file in the run_directory to log information for later
        # analysis of pipeline runs
        _log_pipeline_attributes(
            pipeline_run=run, run_dir=run_dir_set_up, context=context
        )

        self.logger.event(
            "Pipeline completed",
            name=pipeline.name,
            run_id=runtime_id.get_id(),
            stages=len(stage_results),
        )

        return run


def build_parser() -> argparse.ArgumentParser:
    """
    Determines what arguments are needed when running a Pipeline from the command line.

    Enables stages to be input, followed by a name if provided.
    """
    parser = argparse.ArgumentParser(
        description="Run an onsrap pipeline from Python files."
    )
    parser.add_argument(
        "stages", nargs="+", help="One or more Python stage files to run."
    )
    parser.add_argument("--name", default=None, help="Optional pipeline name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Entrypoint to the pipeline.

    This function can be called from the command line. It builds a parser which enables
    the arguments to be held before using those arguments to build a Pipeline instance.
    The pipeline.run() method is then run which runs the entire pipeline. If this runs
    successfully, a 0 is returned which is the success code.

    Parameters
    ----------
    ``argv`` : list[str] or None
        Command line arguments to parse.

    Returns
    -------
    int
        Success code for completion of the run.
    """
    from .pipeline import Pipeline

    args = build_parser().parse_args(argv)
    pipeline = Pipeline.from_files(args.stages, name=args.name)
    pipeline.run()
    return 0


def _log_pipeline_attributes(
    pipeline_run: PipelineRun, run_dir: FileSystemSetUp, context: ExecutionContext
) -> None:
    """
    Creates a YAML file within the run directory that contains information
    regarding PipelineRun and StageResult instances for the run. This is
    later used to extract information about previous runs which are not
    currently stored in memory.

    Parameters
    ----------
    ``pipeline_run`` : PipelineRun
        The PipelineRun instance for the current run of the pipeline.
    ``stage_results`` : list[StageResult]
        A list of StageResult instances for the current run of the pipeline.
    ``run_dir`` : FileSystemSetUp
        The directory where the pipeline run is being currently being executed.
    ``context`` : ExecutionContext
        The context of the current pipeline run, containing configuration and
        state information.
    """
    attributes_file = FileSystemSetUp.confirm_typing(run_dir, path_type="dir")
    attributes_file.file_name = (
        f"pipeline_attributes_for_{context.pipeline_name}_{context.run_id[-8:]}.yaml"
    )
    file_system = FileSystemFactory.create(attributes_file)
    import yaml

    with file_system.open(mode="w", encoding="utf-8") as f:
        yaml.safe_dump(
            pipeline_run._pipeline_run_to_dict(), f, default_flow_style=False
        )


def _log_config(
    run_dir: FileSystemSetUp, context: ExecutionContext, manifest: RunManifest
) -> None:
    """
    Outputs the configurations used in an instance of a pipeline to a YAML file in the run directory.

    The file is kept in the block flow style typically expected of a YAML file.

    Parameters
    ----------
    ``run_dir`` : FileSystemSetUp
        The directory where the pipeline run is being executed.
    ``context`` : ExecutionContext
        The context of the current pipeline run, containing configuration and state information.
    ``manifest`` : RunManifest
        The manifest of the current pipeline run, containing metadata and outputs.
    """
    date = context.started_at.date()
    config_file = FileSystemSetUp(
        prefix=run_dir.prefix,
        root=run_dir.root,
        workspace_path=run_dir.workspace_path,
        file_name=run_dir.file_name,
    )
    config_file.file_name = (
        f"configuration_for_{context.pipeline_name}_{date}_{context.run_id[-8:]}.yaml"
    )
    import yaml

    config_to_dump = _yaml_safe_encode(manifest.config)
    file_system = FileSystemFactory.create(config_file)
    with file_system.open(mode="w", encoding="utf-8") as f:
        yaml.safe_dump(config_to_dump or {}, f, default_flow_style=False)


def _flatten(obj: dict | list, prefix: str = "", sep: str = ".") -> dict:
    """
    Converts nested dictionaries or lists into flat object using dot notation for keys.
    Each key in the resulting dictionary represents the nested branching to get to the value
    in the original dictionary.

    Parameters
    ----------
    ``obj`` : dict or list
        The object to flatten, which can be a dictionary or a list.
    ``prefix`` : str
        The prefix to use for the keys in the flattened dictionary. Defaults to an empty string.
    ``sep`` : str
        The separator to use between keys in the flattened dictionary. Defaults to a dot (".").

    Returns
    -------
    dict
        A flattened dictionary where each key represents the path to the value in the original object.
    """
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            items.update(_flatten(v, f"{prefix}{sep}{k}" if prefix else k, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            items.update(_flatten(v, f"{prefix}[{i}]", sep))
    else:
        items[prefix] = obj
    return items


def _diff_yaml_files(path_a: Path, path_b: Path) -> dict:
    """
    Calculates the differences between two YAML files and returns a programming oriented dictionary
    describing the changes.

    This function calls the  ``_flatten`` function to the loaded in dictionaries from the YAML files.
    These are then differenced to account for whether a value has changed between the two files,
    been added to the second file and was not present in the first, or removed from the second file
    and is only present in the first. This output is structured as {changed: {}, added: {}, removed: {}}.

    Parameters
    ----------
    ``path_a`` : Path
        The path to the first YAML file to compare.
    ``path_b`` : Path
        The path to the second YAML file to compare.

    Returns
    -------
    dict
        A dictionary describing the differences between the two YAML files, structured as
        {changed: {}, added: {}, removed: {}}.
    """
    import yaml

    with open(path_a, encoding="utf-8") as f:
        doc_a = yaml.safe_load(f) or {}
    with open(path_b, encoding="utf-8") as f:
        doc_b = yaml.safe_load(f) or {}

    flat_a = _flatten(doc_a)
    flat_b = _flatten(doc_b)
    keys_a, keys_b = set(flat_a), set(flat_b)

    return {
        "changed": {
            k: (flat_a[k], flat_b[k]) for k in keys_a & keys_b if flat_a[k] != flat_b[k]
        },
        "added": {k: flat_b[k] for k in keys_b - keys_a},
        "removed": {k: flat_a[k] for k in keys_a - keys_b},
    }


def _print_diff(diff: dict) -> dict:
    """
    Prints the differences between two YAML files in a human-readable format and returns
    the computer-readable dictionary so that it could be used for logging processes if
    required.

    Parameters
    ----------
    diff : dict
        A dictionary describing the differences between two YAML files, structured as
        {changed: {}, added: {}, removed: {}}.

    Returns
    -------
    dict
        The same dictionary that was passed in as the ``diff`` parameter.
    """
    changed = diff["changed"]
    added = diff["added"]
    removed = diff["removed"]

    if changed:
        print(f"\nCHANGED ({len(changed)})")
        for key, (val_a, val_b) in sorted(changed.items()):
            print(f"  {key}:  {val_a!r}  →  {val_b!r}")

    if added:
        print(f"\nADDED in second configuration ({len(added)})")
        for key, val in sorted(added.items()):
            print(f"  {key}: {val!r}")

    if removed:
        print(f"\nREMOVED in second configuration ({len(removed)})")
        for key, val in sorted(removed.items()):
            print(f"  {key}: {val!r}")

    if not any([changed, added, removed]):
        print("Files are identical.")

    return diff


def print_config_diffs(file_1, file_2) -> dict:
    """
    A combining function that calculates the differences between two YAML files
    and then prints the outputs to the terminal as well as returning the computer-readable
    dictionary of the differences.

    This works by calling the ``_diff_yaml_files`` function to calculate the differences and
    then calling the ``_print_diff`` function to print the differences.

    Parameters
    ----------
    ``file_1`` : Path
        The path to the first YAML file to compare.
    ``file_2`` : Path
        The path to the second YAML file to compare.

    Returns
    -------
    dict
        A dictionary describing the differences between the two YAML files, structured as
        {changed: {}, added: {}, removed: {}}.
    """
    diff_dict = _diff_yaml_files(file_1, file_2)
    return _print_diff(diff_dict)
