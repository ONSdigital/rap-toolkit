from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rap_toolkit.errors import (
    PipelineConfigurationError,
    StageExecutionError,
    StageLoadError,
)
from rap_toolkit.execution import (
    ExecutionContext,
    PythonStageExecutor,
    _build_success_result,
    _invoke_callable,
)
from rap_toolkit.file_system_setup import FileSystemSetUp
from rap_toolkit.logger import Logger
from rap_toolkit.models import (
    GlobalConfig,
    PipelineConfig,
    StageConfig,
    StageResult,
    StageStatus,
)
from rap_toolkit.stage import Stage
from rap_toolkit.warnings import StageConfigurationWarning


@pytest.fixture
def logger() -> Logger:
    """
    Logger instance for testing
    """
    return Logger()


@pytest.fixture
def config(tmp_path) -> PipelineConfig:
    """
    Return a PipelineConfig object for testing.
    """
    work_dir = FileSystemSetUp.from_path(tmp_path / "work_dir")
    project_root = FileSystemSetUp.from_path(tmp_path / "project_root")
    log_dir = FileSystemSetUp.from_path(tmp_path / "work_dir/log")
    data_dir = FileSystemSetUp.from_path(tmp_path / "work_dir/config_data")
    return PipelineConfig(
        "test_pipeline",
        {"stage_test": True},
        "python",
        work_dir,
        project_root,
        None,
        log_dir,
        data_dir,
        True,
        None,
        {},
    )


@pytest.fixture
def stage_config() -> StageConfig:
    """
    Return a StageConfig object for testing.
    """
    return StageConfig(
        name="stage_test",
        _variables={"sex": "gender", "dob": "date_of_birth"},
        metadata={},
    )


@pytest.fixture
def execution(config, logger, stageresult, stage_config, tmp_path) -> ExecutionContext:
    """
    Create an ExecutionContext object for testing.

    Parameters
    ----------
    ``config`` : PipelineConfig
        A ``PipelineConfig`` object for testing.
    ``logger`` : Logger
        A ``Logger`` object for testing.
    ``stageresult`` : StageResult
        A ``StageResult`` object for testing.
    ``stage_config`` : StageConfig
        A ``StageConfig`` object for testing.
    """
    run_dir = FileSystemSetUp.from_path(tmp_path / "work_dir/runs")
    work_dir = FileSystemSetUp.from_path(tmp_path / "work_dir")

    return ExecutionContext(
        "test_pipeline",
        "run_id_1234",
        config,
        logger,
        run_dir,
        "2024-05-06 15:45:30",
        work_dir,
        {"stage_test": stageresult},
        {"stage_test": stage_config},
        {},
        None,
    )


@pytest.fixture
def stageresult() -> StageResult:
    """
    Test StageResult instance for running ExecutionContext tests.
    """
    return StageResult(
        "stage_test",
        StageStatus.PENDING,
        "2024-05-06 15:45:30",
        "2024-05-07 15:45:30",
        metadata={},
        outputs="example output",
    )


@pytest.fixture
def expected_recorded_stage_result() -> StageResult:
    """
    Expected StageResult after recording for assertions.
    """
    return StageResult(
        name="stage_test",
        status="pending",
        started_at="2024-05-06 15:45:30",
        finished_at="2024-05-07 15:45:30",
        outputs="example output",
        stdout="",
        stderr="",
        return_code=None,
        metadata={},
        error=None,
        source=None,
    )


class TestExecutionContext:
    def test_executioncontext_creation(
        self, execution, logger, config, stageresult, tmp_path
    ) -> None:
        """
        Test that the ExecutionContext creates the right attributes.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``logger`` : Logger
            A ``Logger`` object for testing.
        ``config`` : PipelineConfig
            A ``PipelineConfig`` object for testing.
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        """
        assert execution.pipeline_name == "test_pipeline"
        assert execution.run_id == "run_id_1234"
        assert execution.config == config
        assert execution.logger == logger
        assert execution.run_dir == FileSystemSetUp.from_path(
            tmp_path / "work_dir/runs"
        )
        assert execution.started_at == "2024-05-06 15:45:30"
        assert execution.working_directory == FileSystemSetUp.from_path(
            tmp_path / "work_dir"
        )
        assert execution.stage_results == {"stage_test": stageresult}
        assert execution.variables == {}

    def test_record(
        self, stageresult, execution, expected_recorded_stage_result
    ) -> None:
        """
        Tests that StageResult attributes are attached to stage_results and variables
        attributes in the ExecutionContext instance.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``expected_recorded_stage_result`` : StageResult
            The expected ``StageResult`` object after recording for assertions.
        """
        execution.record(stageresult)
        assert execution.stage_results == {"stage_test": expected_recorded_stage_result}
        assert execution.variables == {"stage_test": "example output"}

    def test_log_exposes_logger_event(self, execution) -> None:
        """
        Tests that ExecutionContext.log forwards custom stage logging to Logger.event.
        """
        execution.logger.event = Mock()

        execution.log("Custom stage message", step="validation")

        execution.logger.event.assert_called_once_with(
            "Custom stage message", step="validation"
        )

    def test_result_for(
        self, execution, stageresult, expected_recorded_stage_result
    ) -> None:
        """
        Tests that result_for correctly extracts the results of a requested stage.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        ``expected_recorded_stage_result`` : StageResult
            The expected ``StageResult`` object after recording for assertions.
        """
        execution.record(stageresult)
        assert execution.result_for("stage_test") == expected_recorded_stage_result

    def test_stage_outputs(self, execution, stageresult) -> None:
        """
        Tests that stage_outputs shows the outputs attribute of the StageResult
        instance for a requested stage is extracted.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        """
        execution.record(stageresult)
        assert execution.stage_outputs == {"stage_test": "example output"}

    @pytest.fixture
    def blank_context_with_config_none(self, stageresult, tmp_path) -> ExecutionContext:
        """
        Fixture that returns a test ExecutionContext instance with a None config for
        testing error handling.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        """
        run_dir = FileSystemSetUp.from_path(tmp_path / "work_dir/runs")
        work_dir = FileSystemSetUp.from_path(tmp_path / "work_dir")
        return ExecutionContext(
            "test_pipeline",
            "run_id_1234",
            None,
            Logger(),
            run_dir,
            "2024-05-06 15:45:30",
            work_dir,
            {"stage_test": stageresult},
            {},
        )

    def test_get_data_dir(
        self, execution, blank_context_with_config_none, tmp_path
    ) -> None:
        """
        Tests that get_data_dir method extracts the path from the execution context
        or, if the context is None, returns an error to indicate that additional input
        is required.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``blank_context_with_config_none`` : ExecutionContext
            An ``ExecutionContext`` object with a None config for testing error
            handling.

        Raises
        ------
        ``PipelineConfigurationError``
            If the config attribute of the ExecutionContext instance is None.
        """
        path = Path(tmp_path / "work_dir/config_data")
        path.mkdir(parents=True, exist_ok=True)
        assert (
            execution.get_data_dir(path_type="uri")
            == FileSystemSetUp.from_path(tmp_path / "work_dir/config_data").create_uri()
        )

        assert (
            execution.get_data_dir(path_type="path")
            == FileSystemSetUp.from_path(
                tmp_path / "work_dir/config_data"
            ).create_path()
        )

        assert (
            execution.get_data_dir(path_type="path")
            == FileSystemSetUp.from_str(
                str(tmp_path / "work_dir/config_data")
            ).create_path()
        )

        with pytest.raises(PipelineConfigurationError):
            blank_context_with_config_none.get_data_dir(path_type="uri")

    def test_resolve_output_root(self, execution, tmp_path) -> None:
        """
        Tests that resolve_output_root method extracts the path from the given run
        directory or, if None are given, raises an error to indicate additional input
        is required.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.

        Raises
        ------
        ``PipelineConfigurationError``
            If the run_dir attribute of the ExecutionContext instance is None.
        """
        work_dir = FileSystemSetUp.from_path(tmp_path / "work_dir")
        path_dir = tmp_path / "work_dir/runs"
        path_dir.mkdir(parents=True, exist_ok=True)
        assert (
            execution.resolve_output_root(path_type="uri")
            == FileSystemSetUp.from_path(tmp_path / "work_dir/runs").create_uri()
        )

        assert (
            execution.resolve_output_root(path_type="path")
            == FileSystemSetUp.from_path(tmp_path / "work_dir/runs").create_path()
        )

        assert (
            execution.resolve_output_root(path_type="path")
            == FileSystemSetUp.from_str(str(tmp_path / "work_dir/runs")).create_path()
        )

        execution_blank_config = ExecutionContext(
            "test_pipeline",
            "run_id_1234",
            None,
            Logger(),
            None,
            "2024-05-06 15:45:30",
            work_dir,
            {"stage_test": stageresult},
            {},
        )

        with pytest.raises(PipelineConfigurationError):
            execution_blank_config.resolve_output_root(path_type="uri")

    def test_stage_config_accessors_return_named_and_active_configs(
        self, config, logger
    ) -> None:
        """
        Tests that getter methods to return the stage_config for a named stage
        returns correct attributes based on given parameters.

        Parameters
        ----------
        ``config`` : PipelineConfig
            A ``PipelineConfig`` object for testing.
        ``logger`` : Logger
            A ``Logger`` object for testing.

        Raises
        ------
        ``PipelineConfigurationError``
            Requested a StageConfig instance as with_global = True, the output must
            be a dictionary however quantifying vars_only as False would demand that
            the entire StageConfig instance is returned.
        """
        stage_config = StageConfig(name="stage_test", _variables={"years_to_run": 2017})
        context = ExecutionContext(
            "test_pipeline",
            "run_id_1234",
            config,
            logger,
            FileSystemSetUp.from_str("work_dir/runs"),
            stage_configs={"stage_test": stage_config},
            active_stage_name="stage_test",
        )

        assert context.stage_config_for("stage_test") == stage_config
        assert context.get_stage_config("stage_test") == {"years_to_run": 2017}
        assert context.get_stage_config() == {"years_to_run": 2017}
        with pytest.raises(PipelineConfigurationError):
            context.get_stage_config(vars_only=False)
        assert (
            context.get_stage_config(with_global=False, vars_only=False) == stage_config
        )

    def test_set_active_stage(self, execution, stage_config) -> None:
        """
        Tests that set_active_stage correctly sets the active_stage attribute in the
        ExecutionContext instance.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stage_config`` : StageConfig
            A ``StageConfig`` object for testing.
        """
        execution.set_active_stage(stage_config.name)
        assert execution.active_stage_name == stage_config.name
        execution.set_active_stage(None)
        assert execution.active_stage_name is None

    def test_stage_config_for(self, execution, stage_config) -> None:
        """
        Tests that stage_config_for returns the StageConfig for a named stage.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stage_config`` : StageConfig
            A ``StageConfig`` object for testing.
        """
        assert execution.stage_config_for(stage_config.name) == stage_config
        assert execution.stage_config_for("missing_stage") is None

    def test_stage_config(self, execution, stage_config) -> None:
        """
        Tests that stage_config exposes the currently active stage configuration.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stage_config`` : StageConfig
            A ``StageConfig`` object for testing.
        """
        assert execution.stage_config is None
        execution.set_active_stage(stage_config.name)
        assert execution.stage_config == stage_config

    def test_get_stage_config(self, execution, stage_config) -> None:
        """
        Tests that get_stage_config returns variables by default and the full
        StageConfig object when requested.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``stage_config`` : StageConfig
            A ``StageConfig`` object for testing.

        Raises
        ------
        ``PipelineConfigurationError``
            Requested a StageConfig instance as with_global = True, the output must
            be a dictionary however quantifying vars_only as False would demand that
            the entire StageConfig instance is returned.

        """
        assert execution.get_stage_config() == {}
        with pytest.raises(PipelineConfigurationError):
            execution.get_stage_config(vars_only=False)
        assert execution.get_stage_config(with_global=False, vars_only=False) is None

        execution.set_active_stage(stage_config.name)
        assert execution.get_stage_config() == {"sex": "gender", "dob": "date_of_birth"}

        assert (
            execution.get_stage_config(with_global=False, vars_only=False)
            == stage_config
        )


class TestResolveGivenPath:
    """
    Parameters for testing multiple add_folder options in
    test_resolve_given_path_add_folders function.
    """

    @pytest.mark.parametrize(
        "add_folder,file_name",
        [
            (["interim", "testing_files"], "clean.py"),
            ("interim", "clean.py"),
            (None, "clean.py"),
            (
                ["interim", "testing_files"],
                None,
            ),
            ("interim", None),
            (None, None),
        ],
    )
    def test_resolve_given_path_add_folders(
        self,
        execution,
        add_folder,
        file_name,
    ) -> None:
        """
        Tests the add_folder functionality for lists, single strings, or None type in
        the resolve_given_path class method as well as when the file_name is a valid
        string or None type.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``add_folder`` : Union[str, List[str], None]
            A string, list of strings, or None type to specify additional folders to
            add to the path.
        ``file_name`` : Union[str, None]
            A string or None type to specify the file name to append to the path.
        ``expected`` : Path
            The expected Path object that should be returned by the method.
        """
        path_name = "data_path"
        root = FileSystemSetUp(
            root="project_root", workspace_path="work_dir/data", ssl_file=None
        )

        base_dir = Path(root.root)
        if root.workspace_path:
            base_dir = base_dir.joinpath(*root.workspace_path.split("/"))

        target_parts: list[str] = []
        if isinstance(add_folder, str):
            target_parts.extend(part for part in add_folder.split("/") if part)
        elif isinstance(add_folder, list):
            target_parts.extend(add_folder)
        if file_name is not None:
            target_parts.append(file_name)

        expected_path = base_dir.joinpath(*target_parts).resolve().as_uri()
        if not target_parts:
            expected_path = base_dir.resolve().as_uri()

        assert (
            execution.resolve_given_path(
                None, path_name, file_name, root, "uri", add_folder
            )
            == expected_path
        )

    def test_resolve_given_path_norm(self, execution) -> None:
        """
        Tests that resolve_given_path returns a file path that has been output in a
        StageResult instance.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        execution.record(
            StageResult(
                "stage_test2",
                StageStatus.PENDING,
                "2024-05-06 15:45:30",
                "2024-05-07 15:45:30",
                metadata={},
                outputs={"data_path": "clean.py"},
            )
        )
        stage_name = "stage_test2"
        path_name = "data_path"
        root = FileSystemSetUp(root="project_root", workspace_path="work_dir/data")

        expected_value = FileSystemSetUp.from_str("clean.py").create_uri()

        expected_value_path = FileSystemSetUp.from_str("clean.py").create_path()

        assert (
            execution.resolve_given_path(stage_name, path_name, None, root, "uri", None)
            == expected_value
        )

        assert (
            execution.resolve_given_path(
                stage_name, path_name, None, root, "path", None
            )
            == expected_value_path
        )


@pytest.fixture
def example_function():
    """
    Test function to pass as a callable stage for execution testing.
    """
    return example_function


@pytest.fixture
def stage_test(example_function) -> Stage:
    """
    Stage object with a callable source for testing dispatch and execution.

    Parameters
    ----------
    ``example_function`` : callable
        A callable function to use as the stage source.

    Returns
    -------
    ``Stage``
        A Stage instance with a callable source.
    """
    return Stage(
        name="callable_stage",
        source=example_function,
        dependencies=[],
        metadata={"info": "example"},
    )


@pytest.fixture
def stage_with_file_source(tmp_path) -> Stage:
    """
    Stage object with a file Path source for testing file-based dispatch.

    Parameters
    ----------
    ``tmp_path`` : Path
        A temporary path provided by pytest for testing file creation.

    Returns
    -------
    ``Stage``
        A Stage instance with a Path source.
    """
    script = tmp_path / "test_stage.py"
    script.write_text("def main():\n    return 'output'\n", encoding="utf-8")

    return Stage(
        name="file_stage",
        source=script,
        dependencies=[],
        metadata={},
    )


@pytest.fixture
def stage_factory(tmp_path):
    """
    Fixture factory for creating Stage instances with different source types.

    Usage:
        stage = stage_factory(source=lambda: None, name="custom_stage")
        stage = stage_factory(source_path="script.py", name="file_stage")

    Parameters
    ----------
    ``tmp_path`` : Path
        A temporary path provided by pytest.

    Returns
    -------
    ``callable``
        A factory function that creates Stage instances.
    """

    def _create_stage(
        source=None,
        source_path=None,
        name="test_stage",
        dependencies=None,
        metadata=None,
        entrypoint=None,
    ):
        if source_path is not None:
            path = tmp_path / source_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def main():\n    pass\n", encoding="utf-8")
            source = path

        return Stage(
            name=name,
            source=source,
            dependencies=dependencies or [],
            metadata=metadata or {},
            entrypoint=entrypoint,
        )

    return _create_stage


@pytest.fixture
def pythonstageexecutor() -> PythonStageExecutor:
    return PythonStageExecutor(("main.py", "run.py"))


class TestPythonStageExecutor:
    def test_pythonstageexecutor_setup(self, pythonstageexecutor) -> None:
        """
        Checks that entrypoints are set correctly in the PythonStageExecutor
        instance.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        """
        assert pythonstageexecutor.preferred_entrypoints == ("main.py", "run.py")

    def test_execute_dispatches_callable_sources(
        self, pythonstageexecutor, stage_test, execution
    ) -> None:
        """
        Tests that execute() dispatches callable sources to _execute_callable.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``stage_test`` : Stage
            A ``Stage`` object with a callable source.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        mock_result = Mock()

        with patch.object(
            pythonstageexecutor, "_execute_callable", return_value=mock_result
        ) as mock_callable:
            result = pythonstageexecutor.execute(stage_test, execution)

        mock_callable.assert_called_once_with(
            stage_test, execution, stage_test.source, stage_test.source_label
        )
        assert result == mock_result

    def test_execute_dispatches_path_sources(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that execute() dispatches Path sources to _execute_file.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.
        """
        script = tmp_path / "test_script.py"
        script.write_text("def main(): pass\n")

        stage = Stage(
            name="file_stage",
            source=script,
            dependencies=[],
            metadata={},
        )

        mock_result = Mock()

        with patch.object(
            pythonstageexecutor, "_execute_file", return_value=mock_result
        ) as mock_file:
            result = pythonstageexecutor.execute(stage, execution)

        mock_file.assert_called_once_with(stage, execution)
        assert result == mock_result

    def test_execute_raises_for_unsupported_source(
        self, pythonstageexecutor, execution
    ) -> None:
        """
        Tests that execute() raises StageExecutionError for invalid sources.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        stage = Stage(
            name="invalid_stage",
            source=None,
            dependencies=[],
            metadata={},
        )

        with pytest.raises(StageExecutionError) as exc_info:
            pythonstageexecutor.execute(stage, execution)

        assert exc_info.value.stage_name == "invalid_stage"
        assert "does not have an executable source" in str(exc_info.value)

    def test_execute_raises_for_integer_source(
        self, pythonstageexecutor, execution
    ) -> None:
        """
        Tests that execute() raises StageExecutionError when source is an invalid type.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.

        Raises
        ------
        ``StageExecutionError``
            When the stage source is not a callable or Path.
        """
        stage = Stage(
            name="bad_stage",
            source=lambda: None,
            dependencies=[],
            metadata={},
        )
        stage.source = 42

        with pytest.raises(StageExecutionError):
            pythonstageexecutor.execute(stage, execution)


class TestCombineVars:
    def test_combine_vars(self, execution) -> None:
        """
        Test that checks that a dictionary is returned, combining values from a global
        configuration and a stage configuration whilst removing any stage specific
        exclusions.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        global_vars = {"global_var1": "value1", "global_var2": "value2"}
        exclusions = {"stage_1": ["global_var2"]}
        stage_vars = {"stage_var1": "value3", "stage_var2": "value4"}
        execution.global_config = GlobalConfig(
            _variables=global_vars, exclusion=exclusions
        )
        execution.stage_configs = {
            "stage_1": StageConfig(name="stage_1", _variables=stage_vars),
        }
        execution.active_stage_name = "stage_1"
        combined_vars = execution._combine_vars()
        assert combined_vars == {
            "stage_var1": "value3",
            "stage_var2": "value4",
            "global_var1": "value1",
        }

    def test_combine_vars_errors(self, execution) -> None:
        """
        Test that confirms that a warning is raised if there is a variable defined in
        both the global and the stage configurations as well as asserting the correct
        values.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.

        Raises
        ------
        ``StageConfigurationWarning``
            If a variable is defined in both the global and stage configurations, a
            warning is raised to indicate that the stage variable will take precedence.
        """
        global_vars = {"global_var1": "value1", "global_var2": "value2"}
        exclusions = {"stage_1": ["global_var2"]}
        stage_vars = {"stage_var1": "value3", "global_var1": "value4"}
        execution.global_config = GlobalConfig(
            _variables=global_vars, exclusion=exclusions
        )
        execution.stage_configs = {
            "stage_1": StageConfig(name="stage_1", _variables=stage_vars),
        }
        execution.active_stage_name = "stage_1"

        with pytest.warns(
            StageConfigurationWarning,
            match="Stage defines variable\\(s\\) that are also defined in global "
            "variables: global_var1\\. Stage variables will take precedence.",
        ):
            combined_vars = execution._combine_vars()
            assert combined_vars == {"stage_var1": "value3", "global_var1": "value4"}

    def test_combine_vars_no_exclusion(self, execution) -> None:
        """
        Test confirming that a dictionary is returned, combining values from a global
        configuration and a stage configuration when there are no exclusions defined.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        global_vars = {"global_var1": "value1", "global_var2": "value2"}
        exclusions = {}
        stage_vars = {"stage_var1": "value3", "stage_var2": "value4"}
        execution.global_config = GlobalConfig(
            _variables=global_vars, exclusion=exclusions
        )
        execution.stage_configs = {
            "stage_1": StageConfig(name="stage_1", _variables=stage_vars),
        }
        execution.active_stage_name = "stage_1"
        combined_vars = execution._combine_vars()
        assert combined_vars == {
            "stage_var1": "value3",
            "stage_var2": "value4",
            "global_var1": "value1",
            "global_var2": "value2",
        }


class TestS3PathSplits:
    def test_extract_bucket_and_key(self, execution) -> None:
        """
        Test that confirms that the S3 bucket and key are correctly extracted from a
        given S3 URI.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        s3_uri = "s3://my-bucket/path/to/my/file.txt"
        bucket, key = execution.extract_bucket_and_key(s3_uri)
        assert bucket == "my-bucket"
        assert key == "path/to/my/file.txt"

    def test_extract_bucket_and_key_s3a(self, execution) -> None:
        """
        Test that confirms that the S3 bucket and key are correctly extracted from a
        given S3 URI with the s3a:// scheme.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        s3_uri = "s3a://my-bucket/path/to/my/file.txt"
        bucket, key = execution.extract_bucket_and_key(s3_uri)
        assert bucket == "my-bucket"
        assert key == "path/to/my/file.txt"

    def test_extract_bucket_and_key_invalid_uri(self, execution) -> None:
        """
        Test that confirms that a ValueError is raised when an invalid S3 URI is
        provided.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        invalid_s3_uri = "invalid://my-bucket/path/to/my/file.txt"
        with pytest.raises(ValueError):
            execution.extract_bucket_and_key(invalid_s3_uri)

    def test_extract_bucket_and_key_missing_bucket(self, execution) -> None:
        """
        Test that confirms that a ValueError is raised when an S3 URI is provided
        without a bucket name.

        Parameters
        ----------
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """
        missing_bucket_uri = "s3://"
        with pytest.raises(ValueError):
            execution.extract_bucket_and_key(missing_bucket_uri)


class TestExecuteCallable:
    def test_execute_callable_success(
        self, pythonstageexecutor, stage_test, execution
    ) -> None:
        """
        Tests that _execute_callable successfully runs a callable stage and returns
        a successful StageResult.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``stage_test`` : Stage
            A ``Stage`` object with a callable source.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def test_callable(context, stage):
            return "test_output"

        stage_test.source = test_callable

        with patch.object(execution.logger, "event"):
            result = pythonstageexecutor._execute_callable(
                stage_test, execution, test_callable, "test_callable_label"
            )

        assert result.status == StageStatus.SUCCEEDED
        assert result.outputs == "test_output"
        assert result.name == stage_test.name
        assert result.source == "test_callable_label"

    def test_execute_callable_failure(
        self, pythonstageexecutor, stage_test, execution
    ) -> None:
        """
        Tests that _execute_callable catches exceptions from the callable and returns
        a failed StageResult with the error message.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``stage_test`` : Stage
            A ``Stage`` object with a callable source.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.

        Raises
        ------
        ``StageExecutionError``
            When the callable raises an exception.
        """

        def failing_callable(context, stage):
            raise ValueError("Test error message")

        stage_test.source = failing_callable

        with (
            patch.object(execution.logger, "event"),
            pytest.raises(StageExecutionError) as exc_info,
        ):
            pythonstageexecutor._execute_callable(
                stage_test, execution, failing_callable, "failing_callable"
            )

        assert exc_info.value.stage_name == stage_test.name
        assert "Callable stage failed" in str(exc_info.value)
        assert exc_info.value.result.status == StageStatus.FAILED
        assert "Test error message" in exc_info.value.result.error


class TestExecuteFile:
    def test_execute_file_with_entrypoint(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_file with a resolvable entrypoint calls _execute_callable
        and returns its result.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.
        """
        script = tmp_path / "stage_script.py"
        script.write_text("def main(context, stage):\n    return 'file_output'\n")

        stage = Stage(
            name="file_stage_with_entry",
            source=script,
            dependencies=[],
            metadata={},
            entrypoint="main",
        )

        mock_result = Mock(spec=StageResult)

        with patch.object(
            pythonstageexecutor, "_execute_callable", return_value=mock_result
        ) as mock_callable:
            result = pythonstageexecutor._execute_file(stage, execution)

        assert result == mock_result
        mock_callable.assert_called_once()

    def test_execute_file_entrypoint_load_failure(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_file raises StageLoadError when the entrypoint cannot
        be loaded.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.

        Raises
        ------
        ``StageLoadError``
            When the Python entrypoint could not be loaded.
        """
        script = tmp_path / "bad_stage.py"
        script.write_text("this is not valid python code {{{")

        stage = Stage(
            name="bad_file_stage",
            source=script,
            dependencies=[],
            metadata={},
            entrypoint="main",
        )

        with pytest.raises(StageLoadError) as exc_info:
            pythonstageexecutor._execute_file(stage, execution)

        assert exc_info.value.stage_name == stage.name
        assert "could not be loaded" in str(exc_info.value)

    def test_execute_file_no_entrypoint_fallback_disabled(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_file raises StageExecutionError when no entrypoint is
        found and subprocess fallback is disabled.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.

        Raises
        ------
        ``StageExecutionError``
            When no callable entrypoint is found and fallback is disabled.
        """
        script = tmp_path / "no_main.py"
        script.write_text("x = 1")

        stage = Stage(
            name="no_entry_stage",
            source=script,
            dependencies=[],
            metadata={},
        )

        execution.config.allow_subprocess_fallback = False

        with pytest.raises(StageExecutionError) as exc_info:
            pythonstageexecutor._execute_file(stage, execution)

        assert exc_info.value.stage_name == stage.name
        assert "subprocess fallback is disabled" in str(exc_info.value)

    def test_execute_file_no_entrypoint_fallback_enabled(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_file falls back to _execute_subprocess when no
        entrypoint is found and fallback is enabled.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.
        """
        script = tmp_path / "no_main.py"
        script.write_text("x = 1")

        stage = Stage(
            name="fallback_stage",
            source=script,
            dependencies=[],
            metadata={},
        )

        execution.config.allow_subprocess_fallback = True
        mock_result = Mock(spec=StageResult)

        with patch.object(
            pythonstageexecutor, "_execute_subprocess", return_value=mock_result
        ) as mock_subprocess:
            result = pythonstageexecutor._execute_file(stage, execution)

        assert result == mock_result
        mock_subprocess.assert_called_once_with(stage, execution)


class TestExecuteSubprocess:
    def test_execute_subprocess_success(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_subprocess successfully runs a Python file and captures
        stdout, stderr, and return code.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.
        """
        script = tmp_path / "success_script.py"
        script.write_text("print('Process output')\nprint('Line 2')")

        stage = Stage(
            name="subprocess_success",
            source=script,
            dependencies=[],
            metadata={},
        )

        # Update execution to use tmp_path for working directory
        execution.working_directory = tmp_path

        with patch.object(execution.logger, "event"):
            result = pythonstageexecutor._execute_subprocess(stage, execution)

        assert result.status == StageStatus.SUCCEEDED
        assert "Process output" in result.outputs
        assert result.return_code == 0
        assert result.name == stage.name

    def test_execute_subprocess_failure(
        self, pythonstageexecutor, execution, tmp_path
    ) -> None:
        """
        Tests that _execute_subprocess captures failure information when a script
        returns non-zero exit code.

        Parameters
        ----------
        ``pythonstageexecutor`` : PythonStageExecutor
            A ``PythonStageExecutor`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        ``tmp_path`` : Path
            A temporary path for testing.

        Raises
        ------
        ``StageExecutionError``
            When subprocess returns a non-zero exit code.
        """
        script = tmp_path / "failing_script.py"
        script.write_text("import sys\nprint('Error message')\nsys.exit(1)")

        stage = Stage(
            name="subprocess_failure",
            source=script,
            dependencies=[],
            metadata={},
        )

        # Update execution to use tmp_path for working directory
        execution.working_directory = tmp_path

        with (
            patch.object(execution.logger, "event"),
            pytest.raises(StageExecutionError) as exc_info,
        ):
            pythonstageexecutor._execute_subprocess(stage, execution)

        assert exc_info.value.stage_name == stage.name
        assert exc_info.value.result.status == StageStatus.FAILED
        assert exc_info.value.result.return_code == 1


class TestInvokeCallable:
    def test_invoke_callable_with_context_keyword(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable correctly passes context via keyword argument
        when the callable has a 'context' parameter.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_with_context(context):
            return context.pipeline_name

        result = _invoke_callable(callable_with_context, stage_test, execution)

        assert result == "test_pipeline"

    def test_invoke_callable_with_ctx_keyword(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable correctly passes context via 'ctx' keyword argument.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_with_ctx(ctx):
            return ctx.run_id

        result = _invoke_callable(callable_with_ctx, stage_test, execution)

        assert result == "run_id_1234"

    def test_invoke_callable_with_stage_keyword(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable correctly passes stage via keyword argument.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_with_stage(stage):
            return stage.name

        result = _invoke_callable(callable_with_stage, stage_test, execution)

        assert result == "callable_stage"

    def test_invoke_callable_with_both_keywords(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable correctly passes both context and stage via
        keyword arguments.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_with_both(context, stage):
            return f"{context.pipeline_name}:{stage.name}"

        result = _invoke_callable(callable_with_both, stage_test, execution)

        assert result == "test_pipeline:callable_stage"

    def test_invoke_callable_no_args(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable calls a no-argument callable without error.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_no_args():
            return "no_args_result"

        result = _invoke_callable(callable_no_args, stage_test, execution)

        assert result == "no_args_result"

    def test_invoke_callable_positional_stage_only(self, stage_test, execution) -> None:
        """
        Tests that _invoke_callable passes stage as the only positional parameter.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_stage_only(task):
            return task.name

        result = _invoke_callable(callable_stage_only, stage_test, execution)

        assert result == "callable_stage"

    def test_invoke_callable_positional_context_only(
        self, stage_test, execution
    ) -> None:
        """
        Tests that _invoke_callable passes context as the only positional parameter.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_ctx_only(ctx):
            return ctx.run_id

        result = _invoke_callable(callable_ctx_only, stage_test, execution)

        assert result == "run_id_1234"

    def test_invoke_callable_positional_both_stage_first(
        self, stage_test, execution
    ) -> None:
        """
        Tests that _invoke_callable correctly orders stage then context for positional
        parameters when both are present.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_stage_context(task, ctx):
            return f"{task.name}:{ctx.run_id}"

        result = _invoke_callable(callable_stage_context, stage_test, execution)

        assert result == "callable_stage:run_id_1234"

    def test_invoke_callable_positional_both_context_first(
        self, stage_test, execution
    ) -> None:
        """
        Tests that _invoke_callable correctly orders context then stage for positional
        parameters when context comes first.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        ``execution`` : ExecutionContext
            An ``ExecutionContext`` object for testing.
        """

        def callable_context_stage(context, stage):
            return f"{context.pipeline_name}:{stage.name}"

        result = _invoke_callable(callable_context_stage, stage_test, execution)

        assert result == "test_pipeline:callable_stage"


class TestBuildSuccessResult:
    def test_build_success_result_non_stageresult_output(self, stage_test) -> None:
        """
        Tests that _build_success_result creates a new StageResult when output is
        not already a StageResult.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        """
        from datetime import datetime

        started = datetime(2024, 5, 6, 15, 45, 30)
        finished = datetime(2024, 5, 6, 16, 45, 30)
        output = {"data": "test_output"}

        result = _build_success_result(
            stage_test, started, finished, output, source="test_source"
        )

        assert result.name == stage_test.name
        assert result.status == StageStatus.SUCCEEDED
        assert result.outputs == output
        assert result.started_at == started
        assert result.finished_at == finished
        assert result.source == "test_source"
        assert result.metadata == stage_test.metadata

    def test_build_success_result_stageresult_output_normalizes_name(
        self, stage_test
    ) -> None:
        """
        Tests that _build_success_result updates the name if the output StageResult
        has a different name than the stage.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        """
        from datetime import datetime

        started = datetime(2024, 5, 6, 15, 45, 30)
        finished = datetime(2024, 5, 6, 16, 45, 30)

        output_result = StageResult(
            name="wrong_name",
            status=StageStatus.PENDING,
            started_at=started,
            finished_at=finished,
            outputs="test",
            metadata={},
        )

        result = _build_success_result(
            stage_test, started, finished, output_result, source="test_source"
        )

        assert result.name == stage_test.name

    def test_build_success_result_stageresult_updates_source(self, stage_test) -> None:
        """
        Tests that _build_success_result adds source to a StageResult that has none.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        """
        from datetime import datetime

        started = datetime(2024, 5, 6, 15, 45, 30)
        finished = datetime(2024, 5, 6, 16, 45, 30)

        output_result = StageResult(
            name=stage_test.name,
            status=StageStatus.PENDING,
            started_at=started,
            finished_at=finished,
            outputs="test",
            metadata={},
            source=None,
        )

        result = _build_success_result(
            stage_test, started, finished, output_result, source="new_source"
        )

        assert result.source == "new_source"

    def test_build_success_result_stageresult_pending_to_succeeded(
        self, stage_test
    ) -> None:
        """
        Tests that _build_success_result converts PENDING status to SUCCEEDED.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object for testing.
        """
        from datetime import datetime

        started = datetime(2024, 5, 6, 15, 45, 30)
        finished = datetime(2024, 5, 6, 16, 45, 30)

        output_result = StageResult(
            name=stage_test.name,
            status=StageStatus.PENDING,
            started_at=started,
            finished_at=finished,
            outputs="test",
            metadata={},
        )

        result = _build_success_result(
            stage_test, started, finished, output_result, source="test_source"
        )

        assert result.status == StageStatus.SUCCEEDED
