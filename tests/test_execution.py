from pathlib import Path
from unittest.mock import Mock

import pytest

from onsrap.errors import PipelineConfigurationError
from onsrap.execution import ExecutionContext, PythonStageExecutor
from onsrap.logger import Logger
from onsrap.models import (
    GlobalConfig,
    PipelineConfig,
    StageConfig,
    StageResult,
    StageStatus,
)
from onsrap.warnings import StageConfigurationWarning


@pytest.fixture
def logger() -> Logger:
    """
    Logger instance for testing
    """
    return Logger()


@pytest.fixture
def config() -> PipelineConfig:
    """
    Return a PipelineConfig object for testing.
    """
    work_dir = Path("tmp/work_dir")
    project_root = Path("tmp/project")
    log_dir = Path("tmp/log")
    data_dir = Path("tmp/config_data")
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
def execution(config, logger, stageresult, stage_config) -> ExecutionContext:
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
    run_dir = Path("tmp/run")
    work_dir = Path("tmp/work_dir")

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
        self, execution, logger, config, stageresult
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
        assert execution.run_dir == Path("tmp/run")
        assert execution.started_at == "2024-05-06 15:45:30"
        assert execution.working_directory == Path("tmp/work_dir")
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
    def blank_context_with_config_none(self, stageresult) -> ExecutionContext:
        """
        Fixture that returns a test ExecutionContext instance with a None config for
        testing error handling.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A ``StageResult`` object for testing.
        """
        run_dir = Path("tmp/run")
        work_dir = Path("tmp/work_dir")
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

    def test_get_data_dir(self, execution, blank_context_with_config_none) -> None:
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
        assert execution.get_data_dir() == Path("tmp/config_data")

        with pytest.raises(PipelineConfigurationError):
            blank_context_with_config_none.get_data_dir()

    def test_resolve_output_root(self, execution) -> None:
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
        work_dir = Path("tmp/work_dir")
        assert execution.resolve_output_root() == Path("tmp/run")

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
            execution_blank_config.resolve_output_root()

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
            Path("tmp/run"),
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
        "add_folder,file_name,expected",
        [
            (
                ["interim", "testing_files"],
                "clean.py",
                Path("tmp/data/interim/testing_files/clean.py"),
            ),
            ("interim", "clean.py", Path("tmp/data/interim/clean.py")),
            (None, "clean.py", Path("tmp/data/clean.py")),
            (
                ["interim", "testing_files"],
                None,
                Path("tmp/data/interim/testing_files"),
            ),
            ("interim", None, Path("tmp/data/interim")),
            (None, None, Path("tmp/data")),
        ],
    )
    def test_resolve_given_path_add_folders(
        self, execution, add_folder, file_name, expected
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
        root = Path("tmp/data")

        assert (
            execution.resolve_given_path(None, path_name, file_name, root, add_folder)
            == expected
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
        root = Path("tmp/data")

        assert execution.resolve_given_path(
            stage_name, path_name, None, root, None
        ) == Path("clean.py")


"""TEST NOT RUN FOR StageExecutor AS COVERED UNDER PythonStageExecutor"""


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
