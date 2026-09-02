import datetime
from pathlib import Path
from textwrap import dedent

import pytest

from onsrap.file_system_setup import FileSystemSetUp
from onsrap.models import (
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    RunManifest,
    RuntimeID,
    StageResult,
    StageStatus,
)

STARTED_AT = datetime.datetime(2024, 5, 6, 15, 45, 30)
FINISHED_AT = datetime.datetime(2024, 5, 7, 15, 45, 30)


class TestStatuses:
    def test_stagestatus(self) -> None:
        """
        Test that stagestatus outputs the correct values.
        """
        assert StageStatus.PENDING == "pending"
        assert StageStatus.RUNNING == "running"
        assert StageStatus.SUCCEEDED == "succeeded"
        assert StageStatus.FAILED == "failed"
        assert StageStatus.SKIPPED == "skipped"

    def test_pipeline_status(self) -> None:
        """
        Test that pipeline status outputs the correct values.
        """
        assert PipelineStatus.PENDING == "pending"
        assert PipelineStatus.RUNNING == "running"
        assert PipelineStatus.SUCCEEDED == "succeeded"
        assert PipelineStatus.FAILED == "failed"


@pytest.fixture
def runtimeID() -> RuntimeID:
    """
    Example RuntimeID instance for testing of other methods.
    """
    return RuntimeID(
        id="abc123",
        timestamp=datetime.datetime(2026, 7, 7, 13, 5, 46),
        hash="fnruw9574893ghkwq234h5kg",
        short_hash="4h5kg",
    )


class TestRuntimeID:
    def test_runtimeID_creation(self, runtimeID) -> None:
        """
        Test that a RuntimeID is correctly created.

        Parameters
        ----------
        ``runtimeID`` : RuntimeID
            A RuntimeID instance for testing.
        """
        assert runtimeID.id == "abc123"
        assert runtimeID.timestamp == datetime.datetime(2026, 7, 7, 13, 5, 46)
        assert runtimeID.hash == "fnruw9574893ghkwq234h5kg"
        assert runtimeID.short_hash == "4h5kg"

    def test_getter_functions_runtimeID(self, runtimeID) -> None:
        """
        Tests all the getter functions for the RuntimeID instance.

        Parameters
        ----------
        ``runtimeID`` : RuntimeID
            A RuntimeID instance for testing.
        """
        assert runtimeID.get_id() == "abc123"
        assert runtimeID.get_timestamp() == datetime.datetime(2026, 7, 7, 13, 5, 46)
        assert runtimeID.get_hash() == "fnruw9574893ghkwq234h5kg"
        assert runtimeID.get_short_hash() == "4h5kg"


@pytest.fixture
def blankpipelineconfig() -> PipelineConfig:
    """
    Blank PipelineConfig instance for class method testing.
    """
    return PipelineConfig()


@pytest.fixture
def expected_pipeline_config() -> PipelineConfig:
    """
    Example PipelineConfig completed class instance for method testing.
    """
    return PipelineConfig(
        name="test_rap",
        backend="python",
        work_dir=FileSystemSetUp.confirm_typing(Path("tmp/work"), path_type="dir"),
        project_root=FileSystemSetUp.confirm_typing(Path("project"), path_type="dir"),
        log_dir=FileSystemSetUp.confirm_typing(Path("tmp/logs"), path_type="dir"),
        data_dir=FileSystemSetUp.confirm_typing(Path("tmp/data"), path_type="dir"),
        allow_subprocess_fallback=True,
        python_executable=None,
        metadata={"variables": ["name", "age"], "num_stages": 6},
    )


@pytest.fixture
def pipelineconfig(expected_pipeline_config) -> PipelineConfig:
    """
    Returns a PipelineConfig instance for testing that is derived
    fromthe expected_pipeline_config fixture. Used as a separate
    fixture to ensure that the behaviour of the from_any() method is
    tested correctly in the TestPipelineConfig class.
    """
    return expected_pipeline_config


@pytest.fixture
def mapping() -> dict:
    """
    Example mapping dictionary for use in testing from_mapping() method.
    """
    return {
        "name": "test_rap",
        "backend": "python",
        "work_dir": Path("tmp/work"),
        "project_root": Path("project"),
        "log_dir": Path("tmp/logs"),
        "data_dir": Path("tmp/data"),
        "allow_subprocess_fallback": True,
        "python_executable": None,
        "metadata": {"variables": ["name", "age"], "num_stages": 6},
    }


class TestPipelineConfig:
    def test_from_any(
        self, mapping, pipelineconfig, blankpipelineconfig, expected_pipeline_config
    ) -> None:
        """
        Test derivation for a PipelineConfig instance using the from_any() method. This
        test checks all methods EXCEPT from_file as this will be covered in another
        test due to creation of a mock file being required.

        Parameters
        ----------
        ``mapping`` : dict
            A dictionary mapping of values for a PipelineConfig instance.

        Raises
        ------
        TypeError
            If the input to from_any() is not of a supported type.
        """
        assert blankpipelineconfig.from_any(None) == PipelineConfig()
        assert blankpipelineconfig.from_any(pipelineconfig) == expected_pipeline_config
        assert blankpipelineconfig.from_any(mapping) == expected_pipeline_config

        with pytest.raises(TypeError):
            blankpipelineconfig.from_any(11)

    def test_from_file_errors(self, tmp_path) -> PipelineConfig:
        """
        Checks that a PipelineConfig instance raises the correct exceptions when a
        file is not found or the file does not contain a dictionary mapping.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.

        Raises
        ------
        ``FileNotFoundError``
            If the file path provided does not exist.

        ``TypeError``
            If the file does not contain a dictionary mapping.
        """

        no_map_pipeline_config = tmp_path / "not_valid.py"
        no_map_pipeline_config.write_text(
            dedent(
                """
                variable = "Hello world"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        fake_file = FileSystemSetUp.from_str("path_not_real")
        no_map_pipeline_config_fssetup = FileSystemSetUp.from_path(
            no_map_pipeline_config
        )
        with pytest.raises(FileNotFoundError):
            PipelineConfig.from_file(fake_file)
        with pytest.raises(TypeError):
            PipelineConfig.from_file(no_map_pipeline_config_fssetup)

    def test_from_file_success(
        self, tmp_path, expected_pipeline_config
    ) -> PipelineConfig:
        """
        Checks that a PipelineConfig instance is created successfully from a mock
        file.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        ``expected_pipeline_config`` : PipelineConfig
            A PipelineConfig instance that is expected to be created from the mock
            file.
        """
        pipeline_config = tmp_path / "configuration.py"
        pipeline_config.write_text(
            dedent(
                """
                    {"name":"test_rap",
                                     "backend":"python",
                                     "work_dir":"tmp/work",
                                     "project_root":"project",
                                     "log_dir":"tmp/logs",
                                     "data_dir":"tmp/data",
                                     "allow_subprocess_fallback":True,
                                     "python_executable": null,
                                     "metadata":{"variables":["name","age"],
                                                 "num_stages":6}
                                                 }
                    """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        pipeline_config_fssetup = FileSystemSetUp.confirm_typing(
            pipeline_config, path_type="file"
        )
        configuration = PipelineConfig.from_file(pipeline_config_fssetup)
        assert configuration == expected_pipeline_config

    def test_to_dict(self, pipelineconfig) -> None:
        """
        Test of to_dict() class method for PipelineConfig that it outputs the
        PipelineConfig values as a dictionary.

        Parameters
        ----------
        ``pipelineconfig`` : PipelineConfig
            A PipelineConfig instance for testing.
        """

        assert pipelineconfig.to_dict() == {
            "name": "test_rap",
            "backend": "python",
            "work_dir": FileSystemSetUp.confirm_typing(
                Path("tmp/work"), path_type="dir"
            ).create_uri(),
            "project_root": FileSystemSetUp.confirm_typing(
                Path("project"), path_type="dir"
            ).create_uri(),
            "output_dir": None,
            "log_dir": FileSystemSetUp.confirm_typing(
                Path("tmp/logs"), path_type="dir"
            ).create_uri(),
            "data_dir": FileSystemSetUp.confirm_typing(
                Path("tmp/data"), path_type="dir"
            ).create_uri(),
            "allow_subprocess_fallback": True,
            "python_executable": None,
            "variables": ["name", "age"],
            "num_stages": 6,
        }


@pytest.fixture
def runmanifest() -> RunManifest:
    """
    Example RunManifest class instance for testing of class method.
    """
    return RunManifest(
        "pipeline",
        "1",
        None,
        ["stage1", "stage2"],
        {"uniqueID": "example"},
        {"input_path": "input/data/example.csv"},
        {"output_path": "output/data/example.csv"},
        "python",
        ["1.3.2"],
        "",
        None,
        None,
    )


@pytest.fixture
def stageresult() -> StageResult:
    """
    Example StageResult instance for tests that use the module-level fixture.
    """
    return StageResult(
        "stage_test",
        StageStatus.PENDING,
        "2024-05-06 15:45:30",
        "2024-05-07 15:45:30",
        metadata={},
        outputs="example output",
    )


class TestStageResult:
    def test_stage_result(self, stageresult: StageResult) -> None:
        """
        Uses a StageResult instance created in test_execution to ensure that
        the class instance is created suitably with required defaults.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A StageResult instance for testing.
        """
        assert stageresult.name == "stage_test"
        assert stageresult.status == "pending"
        assert stageresult.started_at == "2024-05-06 15:45:30"
        assert stageresult.finished_at == "2024-05-07 15:45:30"
        assert stageresult.outputs == "example output"
        assert stageresult.stdout == ""
        assert stageresult.stderr == ""
        assert stageresult.return_code is None
        assert stageresult.metadata == {}
        assert stageresult.error is None
        assert stageresult.source is None

    @pytest.mark.parametrize(
        "status_stage,expected_stage",
        [
            (StageStatus.PENDING, False),
            (StageStatus.RUNNING, False),
            (StageStatus.FAILED, False),
            (StageStatus.SUCCEEDED, True),
            (StageStatus.SKIPPED, False),
        ],
    )
    def test_succeeded(self, stageresult, status_stage, expected_stage) -> None:
        """
        Tests succeeded() method for StageResult which outputs True or False depending
        on the status of the StageResult.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A StageResult instance for testing.
        ``status_stage`` : StageStatus
            A StageStatus value to set the status of the StageResult instance.
        ``expected_stage`` : bool
            The expected boolean output from the succeeded() method based on the
            status of the StageResult instance.
        """
        stageresult.status = status_stage
        assert stageresult.succeeded == expected_stage

    def test_duration_seconds(self, stageresult) -> None:
        """
        Tests that duration_seconds() method calculates the correct duration in seconds
        between the started_at and finished_at attributes of the StageResult instance.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A StageResult instance for testing.
        """
        stageresult.started_at = STARTED_AT
        stageresult.finished_at = FINISHED_AT
        seconds_value = (FINISHED_AT - STARTED_AT).total_seconds()
        assert stageresult.duration_seconds == seconds_value


@pytest.fixture
def pipelinerun(stageresult, runmanifest) -> PipelineRun:
    """
    Creates a PipelineRun instance for testing that is used in the TestPipelineRun
    class.

    Parameters
    ----------
    ``stageresult`` : StageResult
        A StageResult instance for testing.
    ``runmanifest`` : RunManifest
        A RunManifest instance for testing.
    """
    return PipelineRun(
        runmanifest,
        PipelineStatus.SUCCEEDED,
        STARTED_AT,
        FINISHED_AT,
        [stageresult],
        {"stage_test": "example output"},
    )


class TestPipelineRun:
    def test_pipelinerun_configuration(
        self, pipelinerun, runmanifest, stageresult
    ) -> None:
        """
        Checks that the PipelineRun instance is created successfully with the correct
        attributes and values.

        Parameters
        ----------
        ``pipelinerun`` : PipelineRun
            A PipelineRun instance for testing.
        ``runmanifest`` : RunManifest
            A RunManifest instance for testing.
        ``stageresult`` : StageResult
            A StageResult instance for testing.
        """
        assert pipelinerun.manifest == runmanifest
        assert pipelinerun.status == PipelineStatus.SUCCEEDED
        assert pipelinerun.started_at == STARTED_AT
        assert pipelinerun.completed_at == FINISHED_AT
        assert pipelinerun.stage_results == [stageresult]
        assert pipelinerun.stage_outputs == {"stage_test": "example output"}

    def test_result_for(self, pipelinerun, stageresult) -> None:
        """
        Checks that the result_for() method of the PipelineRun instance returns the
        correct StageResult instance when provided with a valid stage name, and returns
        None when the stage name is not found.
        """
        assert pipelinerun.result_for("stage_test") == stageresult
        assert pipelinerun.result_for("not_a_stage") is None

    @pytest.mark.parametrize(
        "status,expected",
        [
            (PipelineStatus.PENDING, False),
            (PipelineStatus.RUNNING, False),
            (PipelineStatus.FAILED, False),
            (PipelineStatus.SUCCEEDED, True),
        ],
    )
    def test_succeeded_pipeline(self, pipelinerun, status, expected) -> None:
        """
        Checks that the succeeded() method of the PipelineRun instance returns the
        correct boolean value based on its status.

        Parameters
        ----------
        ``pipelinerun`` : PipelineRun
            A PipelineRun instance for testing.
        ``status`` : PipelineStatus
            A PipelineStatus value to set the status of the PipelineRun instance.
        ``expected`` : bool
            The expected boolean output from the succeeded() method based on the
            status of the PipelineRun instance.
        """
        pipelinerun.status = status
        assert pipelinerun.succeeded == expected


# TODO: Test _extract_stages_run and all methods in StageConfig class


class TestToFromDictMethods:
    """
    Class to store testing methods for to_dict and from_dict, specifically
    for PipelineRun, RunManifest, and StageResult classes.
    """

    @pytest.fixture
    def runmanifest(self) -> RunManifest:
        return RunManifest(
            "pipeline",
            "1",
            None,
            ["stage1", "stage2"],
            {"uniqueID": "example"},
            {"input_path": "input/data/example.csv"},
            {"output_path": "output/data/example.csv"},
            "python",
            ["1.3.2"],
            "",
            None,
            None,
        )

    @pytest.fixture
    def stageresult(self) -> StageResult:
        return StageResult(
            "stage_test",
            StageStatus.SUCCEEDED,
            datetime.datetime(2024, 5, 6, 15, 45, 30),
            datetime.datetime(2024, 5, 7, 15, 45, 30),
            "example output",
            "",
            "",
            None,
            {},
            None,
            None,
        )

    @pytest.fixture
    def pipelinerun(self, runmanifest, stageresult) -> PipelineRun:
        return PipelineRun(
            runmanifest,
            PipelineStatus.SUCCEEDED,
            datetime.datetime(2024, 5, 6, 15, 45, 30),
            datetime.datetime(2024, 5, 7, 15, 45, 30),
            [stageresult],
            {"stage_test": "example output"},
        )

    def test_runmanifest_to_dict(self, runmanifest) -> None:
        """
        Test that the to_dict method for RunManifest outputs the correct dictionary representation.

        Parameters
        ----------
        ``runmanifest`` : RunManifest
            A RunManifest instance provided by the pytest fixture.
        """
        expected_dict = {
            "rap_name": "pipeline",
            "run_id": "1",
            "git_commit": None,
            "stages_run": ["stage1", "stage2"],
            "parameters": {"uniqueID": "example"},
            "inputs": {"input_path": "input/data/example.csv"},
            "outputs": {"output_path": "output/data/example.csv"},
            "backend": "python",
            "package_versions": ["1.3.2"],
            "timestamp": "",
            "reason": None,
            "user": None,
            "config": None,
        }
        assert runmanifest._runmanifest_to_dict() == expected_dict

    def test_runmanifest_from_dict(self, runmanifest) -> None:
        """
        Test that the from_dict method for RunManifest correctly creates a RunManifest instance from a dictionary representation.

        Parameters
        ----------
        ``runmanifest`` : RunManifest
            A RunManifest instance provided by the pytest fixture.
        """
        runmanifest_dict = {
            "rap_name": "pipeline",
            "run_id": "1",
            "git_commit": None,
            "stages_run": ["stage1", "stage2"],
            "parameters": {"uniqueID": "example"},
            "inputs": {"input_path": "input/data/example.csv"},
            "outputs": {"output_path": "output/data/example.csv"},
            "backend": "python",
            "package_versions": ["1.3.2"],
            "timestamp": "",
            "reason": None,
            "user": None,
            "config": None,
        }
        new_runmanifest = RunManifest._runmanifest_from_dict(runmanifest_dict)
        assert new_runmanifest == runmanifest

    def test_stageresult_to_dict(self, stageresult) -> None:
        """
        Test that the to_dict method for StageResult outputs the correct dictionary representation.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A StageResult instance provided by the pytest fixture.
        """
        expected_dict = {
            "name": "stage_test",
            "status": "succeeded",
            "started_at": "2024-05-06T15:45:30",
            "finished_at": "2024-05-07T15:45:30",
            "outputs": "example output",
            "stdout": "",
            "stderr": "",
            "return_code": None,
            "metadata": {},
            "error": None,
            "source": None,
        }
        assert stageresult._stage_result_to_dict() == expected_dict

    def test_stageresult_from_dict(self, stageresult) -> None:
        """
        Test that the from_dict method for StageResult correctly creates a StageResult instance from a dictionary representation.

        Parameters
        ----------
        ``stageresult`` : StageResult
            A StageResult instance provided by the pytest fixture.
        """
        stageresult_dict = {
            "name": "stage_test",
            "status": "succeeded",
            "started_at": "2024-05-06T15:45:30",
            "finished_at": "2024-05-07T15:45:30",
            "outputs": "example output",
            "stdout": "",
            "stderr": "",
            "return_code": None,
            "metadata": {},
            "error": None,
            "source": None,
        }
        new_stageresult = StageResult._stage_result_from_dict(stageresult_dict)
        assert new_stageresult == stageresult

    def test_pipelinerun_to_dict(self, pipelinerun) -> None:
        """
        Test that the to_dict method for PipelineRun outputs the correct dictionary representation.

        Parameters
        ----------
        ``pipelinerun`` : PipelineRun
            A PipelineRun instance provided by the pytest fixture.
        """
        expected_dict = {
            "manifest": pipelinerun.manifest._runmanifest_to_dict(),
            "status": "succeeded",
            "started_at": "2024-05-06T15:45:30",
            "completed_at": "2024-05-07T15:45:30",
            "stage_results": {
                result.name: result._stage_result_to_dict()
                for result in pipelinerun.stage_results
            },
            "stage_outputs": {"stage_test": "example output"},
        }
        assert pipelinerun._pipeline_run_to_dict() == expected_dict

    def test_pipelinerun_from_dict(self, pipelinerun) -> None:
        """
        Test that the from_dict method for PipelineRun correctly creates a PipelineRun instance from a dictionary representation.

        Parameters
        ----------
        ``pipelinerun`` : PipelineRun
            A PipelineRun instance provided by the pytest fixture.
        """
        pipelinerun_dict = {
            "manifest": pipelinerun.manifest._runmanifest_to_dict(),
            "status": "succeeded",
            "started_at": "2024-05-06T15:45:30",
            "completed_at": "2024-05-07T15:45:30",
            "stage_results": {
                result.name: result._stage_result_to_dict()
                for result in pipelinerun.stage_results
            },
            "stage_outputs": {"stage_test": "example output"},
        }
        new_pipelinerun = PipelineRun._pipeline_run_from_dict(pipelinerun_dict)
        assert new_pipelinerun == pipelinerun
