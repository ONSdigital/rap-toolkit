from __future__ import annotations

import inspect
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pyspark.sql import SparkSession

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp
from onsrap.warnings import StageConfigurationWarning

from .errors import (
    PipelineConfigurationError,
    StageExecutionError,
    StageLoadError,
)
from .loader import (
    PREFERRED_ENTRYPOINTS,
    discover_python_entrypoint,
    load_python_callable,
)
from .logger import Logger
from .models import (
    GlobalConfig,
    PipelineConfig,
    StageConfig,
    StageResult,
    StageStatus,
    now,
)

if TYPE_CHECKING:
    from .stage import Stage


@dataclass
class ExecutionContext:
    """
    Holds information needed to run the pipeline.

    Parameters
    ----------
    ``pipeline_name`` : str
        The name of the pipeline.
    ``run_id`` : str
        The unique identifier for the current run of the pipeline.
    ``config`` : ``PipelineConfig`` class instance
        The configuration required for the pipeline.
    ``logger`` : ``Logger`` class instance
        The logger used for this pipeline run.
    ``run_dir``: Path
        The directory that the run saved to.
    ``file_system`` : FileSystem
        The file system used for this pipeline run.
    ``started_at`` : datetime, default = current time
        The time that the pipeline run started.
    ``working_directory`` : Path, default = current working directory
        The directory that the work is taking place in.
    ``stage_results`` : dict[str, StageResult], default = dict
        Stores the logs for the stage run.
    ``stage_configs`` : dict[str, StageConfig], default = dict
        Stage-name keyed configuration mapping resolved by the ``Pipeline``.
    ``variables`` : dict[str, Any], default = dict
        Stores relevant variables regarding the stage run and their results.
    ``active_stage_name`` : str or None, default = None
        Name of the stage currently being executed. Used to expose ``stage_config``.
    ``global_config`` : ``GlobalConfig`` or None, default = None
        Variables which are parsed to all stages throughout the pipeline.
    """

    pipeline_name: str
    run_id: str
    config: PipelineConfig
    logger: Logger
    run_dir: FileSystemSetUp
    started_at: datetime = field(default_factory=now)
    working_directory: FileSystemSetUp = field(
        default_factory=lambda: FileSystemSetUp()
    )
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    stage_configs: dict[str, StageConfig] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    active_stage_name: str | None = None
    global_config: GlobalConfig | None = None
    spark_session: SparkSession | None = None

    def record(self, result: StageResult) -> StageResult:
        """
        Extracts key information from ``StageResult``.

        Saves all information on the results of the Stage to the ``stage_results`` attribute
        and exclusively metadata outputs regarding the run to the ``variables`` attribute.

        Parameters
        ----------
        ``result`` : ``StageResult``
            An instance of a ``StageResult`` class which is created from the Executor classes (StageExecutor, PythonStageExecutor).

        Returns
        ------
        ``result``
            An unchanged ``StageResult`` instance.
        """
        self.stage_results[result.name] = result
        self.variables[result.name] = result.outputs
        return result

    def result_for(self, stage_name: str) -> StageResult | None:
        """
        Getter function that returns the stage_results for a specific ``Stage``.

        Parameters
        ----------
        ``stage_name`` : str
            The name of the ``Stage`` that you are calling the results for.

        Returns
        -------
        ``stage_results``
            Attribute for the specific `Stage` named.
        """
        return self.stage_results.get(stage_name)

    def set_active_stage(self, stage_name: str | None) -> None:
        """
        Mark the stage currently being executed so ``stage_config`` resolves correctly.
        """
        self.active_stage_name = stage_name

    @property
    def stage_config(self) -> StageConfig | None:
        """
        Return the configuration for the stage currently being executed.

        The preferred access method for this is ``get_stage_config()`` which allows
        for optional arguments to return the full ``StageConfig`` instance or just
        the variables dictionary.

        This property is ``None`` outside an active stage run.
        """
        return self.stage_config_for(self.active_stage_name)

    def stage_config_for(self, stage_name: str | None) -> StageConfig | None:
        """
        Return the configuration registered for ``stage_name``.

        Unlike ``stage_config``, this helper does not depend on the currently
        active stage and can be used to inspect any known stage configuration.

        Parameters
        ----------
        ``stage_name`` : str or None
            Name of the stage whose configuration should be returned.
        """
        if stage_name is None:
            return None
        return self.stage_configs.get(stage_name)

    @property
    def stage_outputs(self) -> dict[str, Any]:
        """
        Creates a ``stage_outputs`` attribute for the ``ExecutionContext`` class.

        Extracts the ```outputs`` attribute from the ``stage_results`` class for each
        ``Stage`` name.

        Returns
        -------
        ``stage_outputs``
            Dictionary containing the name of the stage and the associated outputs of
            the run.
        """
        return {name: result.outputs for name, result in self.stage_results.items()}

    def get_data_dir(self, path_type: str) -> str | Path:
        """
        Establishes the filepath that the data is held in.

        Returns
        -------
        str
            The file path for the location of the data being used in the pipeline.
        """
        if self.config is not None:
            if path_type == "uri":
                uri = self.config.data_dir.create_uri()
                return uri
            if path_type == "path":
                path = self.config.data_dir.create_path()
                if path is None:
                    raise PipelineConfigurationError(
                        f"Your run_dir {self.run_dir} cannot be converted into a Path "
                        f"object. It returns {path}. Please check your file system type."
                    )
                return path

        raise PipelineConfigurationError(
            "Please parse a PipelineConfig instance to the ExecutionContext."
        )

    def resolve_output_root(self, path_type: str) -> str | Path:
        """
        Establishes the filepath that the outputs are going to be saved to.

        Returns
        -------
        str
            The file path for the outputs of the run to be saved to.
        """
        if self.run_dir is not None:
            if path_type == "uri":
                uri = self.run_dir.create_uri()
                return uri
            if path_type == "path":
                path = self.run_dir.create_path()
                if path is None:
                    raise PipelineConfigurationError(
                        f"Your run_dir {self.run_dir} cannot be converted into a Path "
                        f"object. It returns {path} Please check your file system type."
                    )
                return path
            raise ValueError("path_type must be path or uri")

        raise PipelineConfigurationError(
            "Please parse a run directory to the ExecutionContext."
        )

    def get_stage_config(
        self, stage: str | None = None, with_global: bool = True, vars_only: bool = True
    ) -> dict[str, Any] | StageConfig | None:
        """
        Returns the configuration for the stage currently being executed, with optional arguments.

        Optional argument ``vars_only`` can be set to ``False`` to return the full ``StageConfig`` instance,
        rather than just the variables dictionary.

        If you want to access ``metadata`` or ``dataframes`` from the ``StageConfig``, you must set ``vars_only`` to False.

        Parameters
        ----------
        ``stage`` : str
            The name of the stage to get the configuration for.
        ``vars_only`` : bool, default = True
            If True, returns only the variables dictionary from the ``StageConfig``. If False, returns the full ``StageConfig`` instance.

        Returns
        -------
        dict[str, Any] or StageConfig or None
            The parameters contained within the configuration for the currently active stage.
            If ``vars_only`` is set to False, returns the StageConfig object itself, containing all attributes including variables, metadata, and dataframes.
        """
        stage_config: StageConfig | None = (
            self.stage_config_for(stage) if stage is not None else self.stage_config
        )

        if with_global and not vars_only:
            raise PipelineConfigurationError(
                "get_stage_config() cannot return a StageConfig when with_global=True. "
                "Global and stage variables are combined into a dictionary; use vars_only=True "
                "or set with_global=False to retrieve the raw StageConfig object."
            )

        if stage_config is None:
            if with_global:
                return self._combine_vars()
            return {} if vars_only else None
        if with_global:
            return self._combine_vars(stage_config)
        if vars_only:
            return stage_config.variables
        return stage_config

    def resolve_given_path(
        self,
        stage_name: str | None,
        path_name: str | None,
        file_name: str | None,
        root: FileSystemSetUp,
        path_type: str,
        add_folder: list[str] | str | None = None,
    ) -> str:
        """
        Returns a file path for a requested item.

        This investigates the result of a previous stage to extract a selected path.
        If the path is not available, it creates a path using a root previously derived
        in main.py, the chosen directory within the root (optional), and the file path.

        Parameters
        ----------
        ``stage_name`` : str
            The name of the stage where the path was outputted.
        ``path_name`` : str
            The name for the path within the stage results. This will be the key from the
            key/value pair within the output of the previous stage.
        ``file_name`` : str
            The name of the file that you are trying to access the Path for.
        ``root`` : FileSystemSetUp
            The file system setup for the root of the directory. This should be denoted through
            other methods.
        ``path_type`` : str = "Path"
            The type of path to return. Can be either ``uri`` or ``path``. Defaults to Path.
        ``add_folder`` : list[str] | str | None, default = None
            Additional folder name/s to add into the returned file path.

        Returns
        -------
        str
            The file path where data has previously been saved to to allow for extraction of
            that data throughout the pipeline.
        """
        result = self.result_for(stage_name) if stage_name is not None else None
        if not isinstance(root, FileSystemSetUp):
            new_root = FileSystemSetUp.file_system_setup_factory(
                root, path_type="dir", spark_session=self.spark_session
            )
        else:
            new_root = root
        file_system = FileSystemFactory.create(new_root)
        if result is not None and path_name is not None:
            selected_path = result.outputs.get(path_name)
            if isinstance(selected_path, (str, Path)):
                return (
                    FileSystemSetUp.from_any(
                        selected_path, spark_session=self.spark_session
                    ).create_uri()
                    if path_type == "uri"
                    else FileSystemSetUp.from_any(
                        selected_path, spark_session=self.spark_session
                    ).create_path()
                )
        if isinstance(add_folder, list):
            if file_name is not None:
                new_path = str(file_system.join_path(*add_folder, file_name))
                return (
                    FileSystemSetUp.from_any(
                        new_path, spark_session=self.spark_session
                    ).create_uri()
                    if path_type == "uri"
                    else FileSystemSetUp.from_any(
                        new_path, spark_session=self.spark_session
                    ).create_path()
                )
            new_path = str(file_system.join_path(*add_folder))
            return (
                FileSystemSetUp.from_any(
                    new_path, spark_session=self.spark_session
                ).create_uri()
                if path_type == "uri"
                else FileSystemSetUp.from_any(
                    new_path, spark_session=self.spark_session
                ).create_path()
            )
        if isinstance(add_folder, str):
            if file_name is not None:
                return (
                    FileSystemSetUp.from_any(
                        str(file_system.join_path(add_folder, file_name)),
                        spark_session=self.spark_session,
                    ).create_uri()
                    if path_type == "uri"
                    else FileSystemSetUp.from_any(
                        str(file_system.join_path(add_folder, file_name)),
                        spark_session=self.spark_session,
                    ).create_path()
                )
            return (
                FileSystemSetUp.from_any(
                    str(file_system.join_path(add_folder)),
                    spark_session=self.spark_session,
                ).create_uri()
                if path_type == "uri"
                else FileSystemSetUp.from_any(
                    str(file_system.join_path(add_folder)),
                    spark_session=self.spark_session,
                ).create_path()
            )
        if file_name is not None:
            return (
                FileSystemSetUp.from_any(
                    str(file_system.join_path(file_name)),
                    spark_session=self.spark_session,
                ).create_uri()
                if path_type == "uri"
                else FileSystemSetUp.from_any(
                    str(file_system.join_path(file_name)),
                    spark_session=self.spark_session,
                ).create_path()
            )
        return (
            FileSystemSetUp.from_any(
                str(file_system.join_path()), spark_session=self.spark_session
            ).create_uri()
            if path_type == "uri"
            else FileSystemSetUp.from_any(
                str(file_system.join_path()), spark_session=self.spark_session
            ).create_path()
        )

    def _combine_vars(self, stage: StageConfig | None = None) -> dict[str, Any]:
        """
        Private method that combines the global variables and the stage
        variables for the current stage.

        Global variables are extracted from the ``global_config`` attribute
        and any variables which are marked as to be excluded from the exclusion
        attribute are removed. The global variables are then combined with the stage
        specific variables and returned as a dictionary. Conflicts raise a warning
        to alert the user that the stage configuration definition will be used as a
        priority.

        Returns
        -------
        ``combined``: dict[str, Any]
            A dictionary of all variables required for the stage that are sourced
            through the configuration.

        Raises
        ------
        ``StageConfigurationWarning``
            If there are conflicting variables between the global and stage configuration,
            a warning is raised to alert the user that the stage configuration will take
            precedence.
        """
        resolved_stage = stage or self.stage_config
        global_vars: dict[str, Any]
        exclusions: dict[str, Any]
        if self.global_config is not None:
            global_vars, exclusions = self.global_config.get_attributes()
        else:
            global_vars, exclusions = {}, {}
        exclusions = exclusions or {}

        if resolved_stage is None:
            return dict(global_vars)

        stage_exclusions_extract = exclusions.get(resolved_stage.name, [])
        stage_exclusions = [exclusion for exclusion in stage_exclusions_extract]

        combined = {
            key: value
            for key, value in global_vars.items()
            if key not in stage_exclusions
        }
        stage_vars = resolved_stage.variables

        conflicts = stage_vars.keys() & combined.keys()
        if conflicts:
            conflicting = ", ".join(sorted(conflicts))
            warnings.warn(
                f"Stage defines variable(s) that are also defined in global "
                f"variables: {conflicting}. Stage variables will take precedence.",
                StageConfigurationWarning,
            )
        combined.update(stage_vars)
        return combined


class StageExecutor(Protocol):
    """
    Child class of ``Protocol``
    Implementation required
    """

    def execute(self, stage: Stage, context: ExecutionContext) -> StageResult:
        """
        Method to run ``Stage`` however implementation required
        """
        ...


class PythonStageExecutor:
    """
    Class to run Python `Stage`.

    Contains methods that allow automatic running of individual `Stage` processes for
    a pipeline.
    """

    def __init__(self, preferred_entrypoints: tuple[str, ...] = PREFERRED_ENTRYPOINTS):
        self.preferred_entrypoints = preferred_entrypoints

    def __str__(self) -> str:
        return f"PythonStageExecutor: \n         Preferred Entrypoints: {self.preferred_entrypoints})"

    def __repr__(self) -> str:
        return (
            f"PythonStageExecutor(preferred_entrypoints={self.preferred_entrypoints})"
        )

    def execute(self, stage: Stage, context: ExecutionContext) -> StageResult:
        """
        Main function to select how ``Stage`` is run.

        Identifies the type of ``source`` within the ``Stage`` and runs the relevant
        function for that type.

        Parameters
        ----------
        ``stage`` : ``Stage`` class
            The ``Stage`` that is attempting to be run.

        ``context`` : ``ExecutionContext`` class
            The metadata required to run the ``Stage``.

        Return
        ------
        ``StageResult`` instance.

        Raise
        -----
        ``StageExecutionError``
            If the ``source`` is not a Path or a callable object.
        """
        if callable(stage.source):
            return self._execute_callable(
                stage, context, stage.source, stage.source_label
            )

        if isinstance(stage.source, FileSystemSetUp):
            return self._execute_file(stage, context)

        raise StageExecutionError(
            f"Stage '{stage.name}' does not have an executable source.",
            stage_name=stage.name,
            source=stage.source_label,
        )

    def _execute_callable(
        self,
        stage: Stage,
        context: ExecutionContext,
        callable_object: Any,
        source_label: str | None,
    ) -> StageResult:
        """
        Attempt to run a callable object.

        Calls the logger.event() method to record an event and attempts to
        run the callable parsed. If the callable cannot be run, an error is flagged
        and the ``StageResult`` instance created shows a failure. If it can be run,
        the callable is run and the ``StageResult`` instance shows a success.
        Metadata is kept for the attempt including ``duration``, ``name``, ``outputs``,
        ``source``, ``mode`` attempted, and ``errors``.

        Parameters
        ----------
        ``stage`` : ``Stage`` class
            A ``Stage`` class instance for the stage being run.
        ``context`` : ``ExecutionContext`` class
            The metadata required to run the ``Stage``.
        ``callable_object`` : Any
            The callable attempting to be run.
        ``source_label`` : str or None
            The type of ``source`` for the ``Stage``.

        Return
        ------
        ``StageResult`` class instance

        Raise
        -----
        ``StageExecutionError``
            If the callable object cannot be run
        """
        started_at = now()
        context.logger.event(
            "Stage started",
            stage=stage.name,
            mode="callable",
            source=source_label,
        )

        try:
            output = _invoke_callable(callable_object, stage, context)
        except Exception as exc:
            finished_at = now()
            result = StageResult(
                name=stage.name,
                status=StageStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                outputs=None,
                metadata=dict(stage.metadata),
                error=str(exc),
                source=source_label,
            )
            raise StageExecutionError(
                "Callable stage failed.",
                stage_name=stage.name,
                source=source_label,
                original_exception=exc,
                result=result,
            ) from exc

        finished_at = now()
        result = _build_success_result(
            stage,
            started_at,
            finished_at,
            output,
            source=source_label,
        )
        context.logger.event(
            "Stage finished",
            stage=stage.name,
            mode="callable",
            status=result.status.value,
        )
        return result

    def _execute_file(self, stage: Stage, context: ExecutionContext) -> StageResult:
        """
        Attempt to run a file.
        Attempt to run a callable object.

        Calls the logger.event() method to record an event and attempts to run
        the callable parsed. If the callable cannot be run, an error is flagged and
        the ``StageResult`` instance created shows a failure. If it can be run, the
        callable is run and the ``StageResult`` instance shows a success. Metadata
        is kept for the attempt including ``duration``, ``name``, ``outputs``, ``source``,
         ``mode`` attempted, and ``errors``.
        If there is no entrypoint or the entrypoint is not a callable object, an error will be
        raised. ``_execute_subprocess()`` method called if no entrypoint is found. A
        ``StageResult`` instance will be created to log the results of the ``Stage``run regardless
        of success or failure.

        Parameters
        ----------
        ``stage`` : ``Stage`` class
            A ``Stage`` class instance for the stage being run.
        ``context`` : ``ExecutionContext`` class
            The metadata required to run the ``Stage``.

        Return
        ------
        ``StageResult`` class instance

        Raise
        -----
        ``StageLoadError``
            If the entrypoint in the stage is unable to be run.
        ``StageExecutionError``
            If the entrypoint is not found.
        """

        path = stage.source
        path = FileSystemSetUp.file_system_setup_factory(
            path, path_type="file", spark_session=context.spark_session
        )

        assert isinstance(path, FileSystemSetUp)

        if path.file_name and path.file_name.lower().endswith(".py"):
            entrypoint = stage.entrypoint or discover_python_entrypoint(path)
            if entrypoint is not None:
                try:
                    target = load_python_callable(path, entrypoint)
                except Exception as exc:
                    failed_result = StageResult(
                        name=stage.name,
                        status=StageStatus.FAILED,
                        started_at=now(),
                        finished_at=now(),
                        outputs=None,
                        metadata=dict(stage.metadata),
                        error=str(exc),
                        source=str(path),
                    )
                    raise StageLoadError(
                        "Python stage entrypoint could not be loaded.",
                        stage_name=stage.name,
                        source=str(path),
                        original_exception=exc,
                        result=failed_result,
                    ) from exc

                return self._execute_callable(stage, context, target, str(path))

            if not context.config.allow_subprocess_fallback:
                failed_result = StageResult(
                    name=stage.name,
                    status=StageStatus.FAILED,
                    started_at=now(),
                    finished_at=now(),
                    outputs=None,
                    metadata=dict(stage.metadata),
                    error="No callable entrypoint was found in the Python file.",
                    source=str(path),
                )
                raise StageExecutionError(
                    "Python stage has no callable entrypoint and subprocess fallback is disabled.",
                    stage_name=stage.name,
                    source=str(path),
                    result=failed_result,
                )

        return self._execute_subprocess(stage, context)

    def _execute_subprocess(
        self, stage: Stage, context: ExecutionContext
    ) -> StageResult:
        """
        Run the entire Python file for the ``Stage`` from the top.

        Not desired method. Uses black-box design and obfuscates Pipeline running. Please refer
        to Wiki documentation on how to implement callable solutions instead.

        If the ``Stage`` source is a file but does not have a callable entrypoint, this method
        will run the entire script top to bottom. The results of the ``Stage`` are recorded
        as a ``StageResult`` instance and logging processes are complete.

        Parameters
        ----------
        ``stage`` : ``Stage`` class
            A ``Stage`` class instance for the stage being run.
        ``context`` : ``ExecutionContext`` class
            The metadata required to run the ``Stage``.

        Return
        ------
        ``result``
            A ``StageResult`` instance holding information on the ``Stage``.

        Raise
        -----
        ``StageExecutionError``
            If the ``Stage`` script was unable to be run successfully.
        """
        path = stage.source
        assert isinstance(path, FileSystemSetUp)

        started_at = now()
        context.logger.event(
            "Stage started",
            stage=stage.name,
            mode="subprocess",
            source=str(path),
        )

        # TODO: currently subprocess will only work with LFS. Need an alternative for remote
        command = [str(path.create_uri())]
        stage_fs = FileSystemFactory.create(path)
        if stage_fs.suffix().lower() == ".py":
            command = [
                context.config.python_executable or sys.executable,
                str(path.create_path()),
            ]

        completed = subprocess.run(
            command,
            cwd=str(context.working_directory.create_path()),
            capture_output=True,
            text=True,
            check=False,
        )

        finished_at = now()
        result = StageResult(
            name=stage.name,
            status=StageStatus.SUCCEEDED
            if completed.returncode == 0
            else StageStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            outputs=completed.stdout,
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
            metadata=dict(stage.metadata),
            error=None
            if completed.returncode == 0
            else completed.stderr.strip()
            or "Subprocess returned a non-zero exit code.",
            source=str(path),
        )

        context.logger.event(
            "Stage finished",
            stage=stage.name,
            mode="subprocess",
            status=result.status.value,
            return_code=completed.returncode,
        )

        if completed.returncode != 0:
            raise StageExecutionError(
                "Subprocess stage failed.",
                stage_name=stage.name,
                source=str(path),
                result=result,
            )

        return result


def _invoke_callable(
    callable_object: Any, stage: Stage, context: ExecutionContext
) -> Any:
    """
    Assigns appropriate parameters for a callable and runs it.

    Searches for parameter terms that likely refer to context or stage. If none of these are found,
    assigns ``context`` as the first parameter and ``stage`` as the second.

    Parameters
    ----------
    ``callable_object`` : Any
        The callable item that is going to be run.
    ``stage`` : ``Stage`` class
        The ``Stage`` class instance to be a parameter for the ``callable_object``.
    ``context`` : ``ExecutionContext`` class
        The ``ExecutionContext`` class instance to be a parameter for the ``callable_object``.

    Returns
    -------
    ``callable_object``
        An invocation of the ``callable_object`` with appropriately assigned parameters.
    """
    signature = inspect.signature(callable_object)
    parameters = list(signature.parameters.values())

    keyword_arguments: dict[str, Any] = {}
    if "context" in signature.parameters:
        keyword_arguments["context"] = context
    elif "ctx" in signature.parameters:
        keyword_arguments["ctx"] = context

    if "stage" in signature.parameters:
        keyword_arguments["stage"] = stage
    elif "task" in signature.parameters:
        keyword_arguments["task"] = stage

    if keyword_arguments:
        return callable_object(**keyword_arguments)

    positional_parameters = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters
    )

    if not positional_parameters and not has_varargs:
        return callable_object()

    if len(positional_parameters) == 1 and not has_varargs:
        first_name = positional_parameters[0].name.lower()
        if first_name in ("stage", "task"):
            return callable_object(stage)
        return callable_object(context)

    if len(positional_parameters) >= 2 or has_varargs:
        first_name = (
            positional_parameters[0].name.lower() if positional_parameters else ""
        )
        second_name = (
            positional_parameters[1].name.lower()
            if len(positional_parameters) > 1
            else ""
        )
        if first_name in ("stage", "task") and second_name in ("context", "ctx"):
            return callable_object(stage, context)
        if first_name in ("context", "ctx") and second_name in ("stage", "task"):
            return callable_object(context, stage)
        return callable_object(context, stage)

    return callable_object()


def _build_success_result(
    stage: Stage,
    started_at: datetime,
    finished_at: datetime,
    output: Any,
    *,
    source: str | None = None,
) -> StageResult:
    """
    Create a ``StageResult`` instance showing a successful stage run.

    If the output of a ``Stage`` run is a ``StageResult`` class, set missing attributes to relevant
    information from the ``Stage``.

    Parameters
    ----------
    ``stage`` : ``Stage`` class
        The ``Stage`` class instance being run.
    ``started_at`` : datetime
        The time and date that the run started.
    ``finished_at`` : datetime
        The time and date that the run ended.
    ``output`` : Any
        The output produced from the stage run.
    ``source`` : str or None
        The file/callable being run in the stage.

    Return
    ------
    ``StageResult`` instance
        Containing metadata for the stage run and showing that the run was a success.
    """
    if isinstance(output, StageResult):
        if output.name != stage.name:
            output.name = stage.name
        if output.source is None:
            output.source = source
        if output.status == StageStatus.PENDING:
            output.status = StageStatus.SUCCEEDED
        return output

    return StageResult(
        name=stage.name,
        status=StageStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        outputs=output,
        metadata=dict(stage.metadata),
        source=source,
    )
