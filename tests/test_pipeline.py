import warnings
from pathlib import Path
from unittest import mock

import pytest

from onsrap.errors import (
    HistoricalPipelineLoadError,
    PipelineConfigurationError,
    PipelineInitialisationError,
    StageLoadError,
)
from onsrap.execution import PythonStageExecutor
from onsrap.file_system_setup import FileSystemSetUp
from onsrap.models import PipelineRun, StageConfig
from onsrap.pipeline import Pipeline, PipelineConfig
from onsrap.stage import Stage
from onsrap.warnings import PipelineConfigurationWarning, StageConfigurationWarning

NO_STAGES_WARNING = "No stages specified to run. All stages running by default."


@pytest.fixture
def stage_factory():
    def _build_stage(name: str, dependencies=(), source: Path | None = None) -> Stage:
        """
        Function that builds a Stage object with a given name, dependencies, and a
        source file path that's built out of the name if it is not provided. This
        standardises the creation of Stage objects for testing.

        Parameters
        ----------
        ``name`` : str
            The name of the stage to be created.
        ``dependencies`` : tuple
            A tuple of stage names that the created stage depends on.
        ``source`` : Path | None
            A Path object representing the source file for the stage. If None, a default
            source file path is created based on the stage name.
        """
        resolved_source = source if source is not None else Path(f"{name}.py")
        return Stage(name, source=resolved_source, dependencies=dependencies)

    return _build_stage


class TestPipelineNamingAndInit:
    def test_pipeline_name(self):
        """
        Test to confirm that Pipeline instance uses either defined name from
        instance creation (shown in pipeline_named), utilises name from PipelineConfig
        if no name was given (shown in pipeline_config), or defaults to "pipeline" if
        no name is provided through Pipeline instance creation or through the
        PipelineConfig (shown through pipeline_no_name)

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.

        """
        pipeline_config = PipelineConfig(name="test_pipeline_config")

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline_named = Pipeline(
                name="test_pipeline_name",
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
            )
            pipeline_config = Pipeline(
                name=None,
                config=pipeline_config,
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
            )
            pipeline_no_name = Pipeline(
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())]
            )

        assert pipeline_named.name == "test_pipeline_name"
        assert pipeline_config.name == "test_pipeline_config"
        assert pipeline_no_name.name == "pipeline"

    def test_assign_dependencies(self, tmp_path):
        """
        Test to ensure that different formats of dependencies can be parsed to the
        Pipeline creation and appropriately assigned to each stage within the
        Pipeline. Will also check for error raise if the dependencies are defined
        but there are no defined stages.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for testing.

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        'PipelineInitialisationError'
            Expected and asserted as there are no stages defined in the Pipeline
            but there are dependencies.
        """

        def example_function():
            pass

        path_1 = tmp_path / "Stage_1.py"
        path_0 = tmp_path / "Stage_0.py"

        dependencies_single = {"Stage_2": ("Stage_1",)}
        dependencies_multiple = {
            "Stage_1": ["Stage_0"],
            "Stage_2": ("Stage_1", "Stage_0"),
        }
        dependencies_non_stage_name = {
            "Stage_1.py": ("Stage_0",),
            "example_function": ("Stage_1.py",),
        }

        with (
            pytest.raises(PipelineInitialisationError),
            pytest.warns(PipelineConfigurationWarning),
        ):
            Pipeline(stages=None, dependencies=dependencies_single)

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline_1 = Pipeline(
                name="pipeline_1",
                stages=[
                    Stage("Stage_1", path_1, None, {}),
                    Stage("Stage_2", example_function, None, {}),
                    Stage("Stage_0", path_0, None, {}),
                ],
                dependencies=dependencies_multiple,
            )

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline_2 = Pipeline(
                name="pipeline_2",
                stages=[
                    Stage("Stage_1.py", path_1, None, {}),
                    Stage("Stage_2", example_function, None, {}),
                    Stage("Stage_0", path_0, None, {}),
                ],
                dependencies=dependencies_non_stage_name,
            )

        assert pipeline_1.stages[0].dependencies == ("Stage_0",)
        assert pipeline_1.stages[1].dependencies == ("Stage_1", "Stage_0")

        assert pipeline_2.stages[0].dependencies == ("Stage_0",)
        assert pipeline_2.stages[1].dependencies == ("Stage_1.py",)

    def test_assign_dependencies_with_config_defined_stages(self, tmp_path):
        """
        Test to ensure dependencies can be assigned when stages are loaded from
        the pipeline configuration rather than passed directly to the constructor.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for testing.
        """

        first_stage = tmp_path / "first_stage.py"
        first_stage.write_text(
            "def run(context):\n    return 'alpha'\n", encoding="utf-8"
        )

        second_stage = tmp_path / "second_stage.py"
        second_stage.write_text(
            "def run(context):\n    return 'beta'\n", encoding="utf-8"
        )

        config_file = tmp_path / "conf.yaml"
        config_file.write_text(
            "\n".join(
                [
                    "pipeline_variables:",
                    f'  work_dir: "{tmp_path.as_posix()}"',
                    f'  project_root: "{tmp_path.as_posix()}"',
                    f'  log_dir: "{(tmp_path / "logs").as_posix()}"',
                    "  stages:",
                    "    - first_stage:",
                    f'        location: "{first_stage.as_posix()}"',
                    "    - second_stage:",
                    f'        location: "{second_stage.as_posix()}"',
                    "stage_configuration: {}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                config=config_file,
                dependencies={"second_stage": ("first_stage",)},
            )

        assert [stage.name for stage in pipeline.stages] == [
            "first_stage",
            "second_stage",
        ]
        assert pipeline.stages[1].dependencies == ("first_stage",)
        assert pipeline.dependencies == {"second_stage": ("first_stage",)}

    def test_add_dependencies_single_dict(self, tmp_path):
        """
        Tests that a dictionary correctly assigns dependencies to
        individual stages and the Pipeline instance.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for testing.

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        'PipelineInitialisationError'
            Expected and asserted as dependencies are specified for stages that do not
            exist in the Pipeline instance.
        """

        path_1 = tmp_path / "Stage_1.py"
        path_2 = tmp_path / "Stage_2.py"
        path_0 = tmp_path / "Stage_0.py"

        dependencies_multiple = {"Stage_0": (), "Stage_1": (), "Stage_2": ("Stage_1",)}
        dep_dict = {"Stage_1": ("Stage_0",), "Stage_2": ("Stage_0", "Stage_1")}
        dep_tuple = ("Stage_0.25",)
        stage_1 = Stage("Stage_1", source=path_1, dependencies={})
        stage_2 = Stage("Stage_2", source=path_2, dependencies={})
        stage_0 = Stage("Stage_0", source=path_0, dependencies={})

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline_dict = Pipeline(
                stages=[stage_0, stage_1, stage_2],
                dependencies=dependencies_multiple,
            )

        with pytest.raises(PipelineInitialisationError):
            pipeline_dict.add_dependencies(dep_tuple)

        with pytest.warns(PipelineConfigurationWarning):
            pipeline_dict.add_dependencies(dep_dict)
        assert stage_1.dependencies == ("Stage_0",)
        assert stage_2.dependencies == (
            "Stage_1",
            "Stage_0",
        )
        assert stage_0.dependencies == ()
        assert pipeline_dict.dependencies == {
            "Stage_0": (),
            "Stage_1": ("Stage_0",),
            "Stage_2": (
                "Stage_1",
                "Stage_0",
            ),
        }


class TestPipelineStageConfigHandling:
    def test_add_stage_parses_stage_configs_keyword(self, stage_factory) -> None:
        """
        Tests that when a stage is added after a Pipeline has been initialised,
        the stage and the stage_configurations are correctly added to the
        Pipeline instance and the stage_configurations are correctly associated
        with the stage.

        Parameter
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())]
            )

        stage = stage_factory("Stage_1")
        stage_config = StageConfig(name="Stage_1", _variables={"years_to_run": 2017})
        with pytest.warns(PipelineConfigurationWarning):
            pipeline.add_stage(stage, stage_configs=[stage_config])

        assert pipeline.stages[-1].name == "Stage_1"
        assert pipeline.stage_configs["Stage_1"].require("years_to_run") == 2017

    def test_add_stage_warns_when_stage_config_count_mismatches(
        self, stage_factory
    ) -> None:
        """
        Tests that when a stage is added but there is not the correct number of
        stage_configs provided, a warning is raised and the stage_configuration
        for that stage is added as a blank StageConfig object.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[
                    Stage("Stage_0_5", source=Path("Stage_0_5.py"), dependencies=())
                ]
            )
            stage_0 = stage_factory("Stage_0")
            stage_1 = stage_factory("Stage_1")

            with pytest.warns(StageConfigurationWarning) as recorded_warnings:
                pipeline.add_stage(
                    stage_0, stage_1, stage_configs=[{"years_to_run": 2017}]
                )

            assert any(
                "does not match the number of stages" in str(recorded_warning.message)
                for recorded_warning in recorded_warnings
            )
            assert pipeline.stage_configs["Stage_0"].require("years_to_run") == 2017
            assert pipeline.stage_configs["Stage_1"].to_dict() == {}

    def test_add_stage_config_coerces_mapping_payload_for_named_stage(
        self, stage_factory
    ) -> None:
        """
        Tests that when a stage_configuration is added to a Pipeline instance,
        the configuration is correctly associated with the named stage and that
        the configuration is coerced into a StageConfig object if it is provided.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        'PipelineConfigurationWarning'
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        pipeline.add_stage_config({"years_to_run": 2017}, name="Stage_0")

        assert pipeline.stage_configs["Stage_0"].require("years_to_run") == 2017


class TestPipelineStageSelectionAndGraph:
    def test_resolve_stages_to_run_includes_transitive_dependencies(
        self, stage_factory
    ) -> None:
        """
        Tests that when resolving stages_to_run, the Pipeline instance correctly
        includes all dependent stages required in the StageGraph even if these
        are not explicitly called out in the configuration.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.
        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1", dependencies=("Stage_0",))
        stage_2 = stage_factory("Stage_2", dependencies=("Stage_1",))

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0, stage_1, stage_2],
                config=PipelineConfig(stages_to_run={"Stage_2": True}),
            )

        assert [stage.name for stage in pipeline.graph.stages] == [
            "Stage_0",
            "Stage_1",
            "Stage_2",
        ]
        assert [stage.name for stage in pipeline.ordered_stages()] == [
            "Stage_0",
            "Stage_1",
            "Stage_2",
        ]

    def test_resolve_stages_to_run_rejects_disabled_dependencies(
        self, stage_factory
    ) -> None:
        """
        Checks that when resolving stages_to_run, the Pipeline init raises an
        error if a stage is enabled but one of its dependencies is disabled.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        ``PipelineConfigurationError``
            Raised when a stage is enabled but one of its dependencies is disabled.
        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1", dependencies=("Stage_0",))

        with pytest.raises(PipelineConfigurationError):
            Pipeline(
                stages=[stage_0, stage_1],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": False, "Stage_1": True}
                ),
            )

    def test_self_stages_is_full_registry_after_disable(self, stage_factory) -> None:
        """
        Pipeline.stages always holds all stages; only graph.stages is the effective run
        set.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1")

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_0, stage_1])

        pipeline.disable_stage("Stage_1")

        assert [stage.name for stage in pipeline.stages] == ["Stage_0", "Stage_1"]
        assert [stage.name for stage in pipeline.graph.stages] == ["Stage_0"]
        assert [stage.name for stage in pipeline.ordered_stages()] == ["Stage_0"]

    def test_disable_stage_in_implicit_mode_creates_explicit_selection(
        self, stage_factory
    ) -> None:
        """
        Tests that when a stage is manually disabled in a Pipeline instance, it
        is initialised in the stages_to_run configuration.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Expected and asserted as there is no stage run specification in the
            Pipeline configuration. This does not affect the test capability.
        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1")
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_0, stage_1])

        pipeline.disable_stage("Stage_1")

        assert pipeline.config.stages_to_run == {"Stage_0": True, "Stage_1": False}

    def test_enable_stage_restores_stage_in_explicit_mode(self, stage_factory) -> None:
        """
        Tests that when a stage is manually enabled in a Pipeline instance, it
        is correctly reflected in the stages_to_run configuration and the stage
        is included in the execution graph.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1")
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0, stage_1],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": True, "Stage_1": False}
                ),
            )

        pipeline.enable_stage("Stage_1")

        assert pipeline.config.stages_to_run["Stage_1"] is True
        assert {stage.name for stage in pipeline.graph.stages} == {"Stage_0", "Stage_1"}

    def test_add_stage_keeps_new_stage_out_of_explicit_selection(
        self, stage_factory
    ) -> None:
        """
        Tests that when a new stage is added to a Pipeline instance, it is
        kept out of the explicit selection.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        """
        stage_0 = stage_factory("Stage_0")
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0],
                config=PipelineConfig(stages_to_run={"Stage_0": True}),
            )

            pipeline.add_stage(
                stage_factory("Stage_1"),
                stage_configs=[StageConfig(name="Stage_1")],
            )

        assert pipeline.config.stages_to_run["Stage_1"] is False
        assert [stage.name for stage in pipeline.graph.stages] == ["Stage_0"]

    def test_add_stage_adds_new_stage_to_explicit_selection_when_enable_stages_is_true(
        self,
        stage_factory,
    ) -> None:
        """
        Tests that when a new stage is added to a Pipeline instance with
        enable_stages=True, it is included in the explicit selection.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.

        """
        stage_0 = stage_factory("Stage_0")
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0],
                config=PipelineConfig(stages_to_run={"Stage_0": True}),
            )

            pipeline.add_stage(
                stage_factory("Stage_1"),
                stage_configs=[StageConfig(name="Stage_1")],
                enable_stages=True,
            )

        assert pipeline.config.stages_to_run["Stage_1"] is True
        assert {stage.name for stage in pipeline.graph.stages} == {"Stage_0", "Stage_1"}


class TestPipelineValidationAndManifest:
    def test_validate_skips_source_check_for_disabled_stages(
        self, tmp_path: Path
    ) -> None:
        """
        Disabled stages' source files need not exist - validate() only checks the
        effective run set.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files.
        """
        enabled_file = tmp_path / "Stage_0.py"
        enabled_file.write_text("def run(ctx): pass\n", encoding="utf-8")

        stage_0 = Stage("Stage_0", source=enabled_file)
        stage_1 = Stage(
            "Stage_1", source=tmp_path / "missing.py"
        )  # file intentionally absent

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0, stage_1],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": True, "Stage_1": False}
                ),
            )

        pipeline.validate()  # must not raise

    def test_construct_manifest_inputs_contains_only_effective_stages(
        self, stage_factory
    ) -> None:
        """
        Manifest inputs should list only the stages that are part of the execution
        graph.

        Parameters
        ----------
        ``stage_factory`` : Callable
            A factory function that creates Stage objects for testing.
        """
        stage_0 = stage_factory("Stage_0")
        stage_1 = stage_factory("Stage_1", dependencies=("Stage_0",))

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_0, stage_1],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": True, "Stage_1": False}
                ),
            )

        runtime_id = pipeline._create_runtime_id()
        manifest = pipeline._construct_manifest(runtime_id=runtime_id)

        assert list(manifest.inputs.keys()) == ["Stage_0"]

    def test_generate_context_correctly_assigns_executor(
        self,
    ) -> None:
        """
        Test that the correct executor class is assigned to the Pipeline instance
        based on the backend specified. If the backend does not have a compatible
        executor, an error is raised.
        """

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                backend="python",
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
            )
        assert isinstance(pipeline.executor, PythonStageExecutor)

        with pytest.raises(PipelineInitialisationError):
            Pipeline(
                backend="nonexistent_backend",
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
            )

    def test_validate_stage_backends_errors(self) -> None:
        """
        Test that the _validate_stage_backends method correctly raises an error if
        the backends for a stage do not match the Pipeline backend or if there are
        multiple backends across the stages.

        Successful runs not tested here as they are covered in test_generate_context_
        correctly_assigns_executor().
        """

        with pytest.raises(PipelineInitialisationError):
            Pipeline(
                backend="python",
                stages=[
                    Stage(
                        "Stage_0",
                        source=Path("Stage_0.py"),
                        dependencies=(),
                        backend="nonexistent_backend",
                    )
                ],
            )

        with pytest.raises(PipelineInitialisationError):
            Pipeline(
                backend="python",
                stages=[
                    Stage(
                        "Stage_0",
                        source=Path("Stage_0.py"),
                        dependencies=(),
                        backend="nonexistent_backend",
                    ),
                    Stage(
                        "Stage_1",
                        source=Path("Stage_1.py"),
                        dependencies=(),
                        backend="python",
                    ),
                ],
            )


class TestLoadLatestRunIntegration:
    @pytest.fixture
    def pipeline_log_line(self):
        def _make(run_id: str, timestamp: str) -> str:
            """
            Returns a false log file line to simulate a historical run in the log file.
            The line is formatted to match the expected log output.

            Parameters
            ----------
            ``run_id`` : str
                The unique identifier for the historical run.
            ``timestamp`` : str
                The timestamp of when the historical run was initiated.
            """
            return (
                f"{timestamp} Pipeline started | "
                f'{{"run_id": "{run_id}", "run_dir": "/path/to/run"}}'
            )

        return _make

    @pytest.fixture
    def minimal_pipeline_yaml(self):
        def _make(run_id: str) -> str:
            """
            Returns a minimal YAML configuration for a historical run.

            Parameters
            ----------
            ``run_id`` : str
                The unique identifier for the historical run.
            """
            return f"""
                    manifest:
                        run_id: {run_id}
                    status: succeeded
                    started_at: '2026-08-06T17:03:30.000077'
                    completed_at: '2026-08-06T17:03:30.031654'
                    stage_results: {{}}
                    stage_outputs: {{}}
                    """

        return _make

    @pytest.fixture
    def pipeline_no_history(self, tmp_path: Path) -> Pipeline:
        """
        Sets up a blank pipeline instance for testing that accounts for warnings
        in init phase rather than dealing with these in the tests.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(
                    output_dir=tmp_path / "outputs",
                ),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )
        return pipeline


class TestLoadLatestRun(TestLoadLatestRunIntegration):
    def test_blank_historical_run_ids(
        self, pipeline_no_history: Pipeline, monkeypatch
    ) -> None:
        """
        Tests that if extract_historical_run_ids returns a blank list, the
        _load_latest_run method will return None and raise a warning. Assert
        that it will also store None in the last_run attribute of the Pipeline
        instance.

        Parameters
        ----------
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when no previous runs are found for the Pipeline, indicating
            that the last_run attribute will be None.
        """
        monkeypatch.setattr(
            pipeline_no_history.logger, "extract_historical_run_ids", lambda x, y: []
        )
        assert (
            pipeline_no_history.logger.extract_historical_run_ids(
                pipeline_no_history.run_output, pipeline_no_history.name
            )
            == []
        )
        with pytest.warns(
            PipelineConfigurationWarning,
            match="No previous runs "
            "found for this Pipeline. Last_run attribute will be None.",
        ):
            assert pipeline_no_history._load_latest_run() is None
            assert pipeline_no_history.last_run is None

    def test_blank_run_ids(self, pipeline_no_history: Pipeline, monkeypatch) -> None:
        """
        Tests that if the found log record does not have a run_id, _load_latest_run
        will return None and raise a warning. Assert that it will also store None
        in the last_run attribute of the Pipeline instance.

        Parameters
        ----------
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when no previous runs are found for the Pipeline, indicating
            that the last_run attribute will be None.
        """
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": None,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/"),
                }
            ],
        )
        assert pipeline_no_history.logger.extract_historical_run_ids(
            pipeline_no_history.run_output, pipeline_no_history.name
        ) == [
            {
                "run_id": None,
                "timestamp": "2026-08-10 10:00:00,000",
                "run_dir": Path("/"),
            }
        ]
        with pytest.warns(
            PipelineConfigurationWarning,
            match="No previous runs "
            "found for this Pipeline. Last_run attribute will be None.",
        ):
            assert pipeline_no_history._load_latest_run() is None
            assert pipeline_no_history.last_run is None

    def test_load_latest_run_success(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Tests that load_latest_run works successfully with fully mocked data.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        """

        expected_run = mock.MagicMock(spec=PipelineRun)
        run_id = "2026-08-10_100000_abc12345"
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": run_id,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run"),
                }
            ],
        )

        mock_load_historical_run = mock.MagicMock(return_value=expected_run)
        monkeypatch.setattr(
            "onsrap.pipeline.load_historical_run", mock_load_historical_run
        )

        result = pipeline_no_history._load_latest_run()

        assert result is expected_run

        expected_path = (
            FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/"
            + run_id
        )
        mock_load_historical_run.assert_called_once_with(run_dir=expected_path)

    def test_which_run_is_selected_load_latest_run(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Checks that the first item is selected from the list of historical runs
        returned by extract_historical_run_ids.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        """
        expected_run = mock.MagicMock(spec=PipelineRun)
        run_id_1 = "2026-08-10_100000_abc12345"
        run_id_2 = "2026-08-10_100000_def67890"
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": run_id_1,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": "run_A",
                },
                {
                    "run_id": run_id_2,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": "run_B",
                },
            ],
        )

        mock_load_historical_run = mock.MagicMock(return_value=expected_run)
        monkeypatch.setattr(
            "onsrap.pipeline.load_historical_run", mock_load_historical_run
        )

        pipeline_no_history._load_latest_run()

        expected_path = (
            FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/"
            + str(run_id_1)
        )
        mock_load_historical_run.assert_called_once_with(run_dir=expected_path)

        # does not refer to run_dir in the extract_historical_run_ids list but the
        # parameter required in load_historical_run.
        assert mock_load_historical_run.call_args.kwargs["run_dir"].endswith(run_id_1)

    def test_no_errors_raised_success_load_latest_run(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Tests that no errors are raised when load_latest_run is successful.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        """

        expected_run = mock.MagicMock(spec=PipelineRun)
        run_id = "2026-08-10_100000_abc12345"
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": run_id,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run"),
                }
            ],
        )

        mock_load_historical_run = mock.MagicMock(return_value=expected_run)
        monkeypatch.setattr(
            "onsrap.pipeline.load_historical_run", mock_load_historical_run
        )

        with warnings.catch_warnings(record=True) as w:
            pipeline_no_history._load_latest_run()

        assert not any(
            issubclass(warning.category, PipelineConfigurationWarning) for warning in w
        )


class TestLoadLatestIntegrationInPipeline(TestLoadLatestRunIntegration):
    def test_no_previous_runs_pipeline(self, tmp_path: Path) -> None:
        """
        Tests that if a Pipeline instance has no previous runs, the _load_latest_run
        method will return None and raise a warning. Assert that it will also store
        None in the last_run attribute of the Pipeline instance.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when no previous runs are found for the Pipeline, indicating
            that the last_run attribute will be None.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )
        assert pipeline.last_run is None

    def test_last_run_populated_one_run(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Tests that if a Pipeline instance has one previous run, this is loaded in
        last_run attribute at Pipeline creation.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is no stages_to_run parameters to warn the user that
            all stages will be run by default.
        """
        logs = tmp_path / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "onsrap.log").write_text(
            "2026-08-11 10:00:00,000 Pipeline started | "
            '{"run_id": "2026-08-11_100000_abc12345", '
            '"name": "test_pipeline", '
            ' "run_dir": "/path/to/run"}\n'
        )

        temp_attributes = (
            tmp_path
            / "outputs"
            / "runs"
            / "2026-08-11_100000_abc12345"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes.write_text(
            minimal_pipeline_yaml(run_id="2026-08-11_100000_abc12345"), encoding="utf-8"
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs", log_dir=logs),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline.last_run is not None
        assert pipeline.last_run.manifest.run_id == "2026-08-11_100000_abc12345"

    def test_last_run_most_recent(self, tmp_path: Path, minimal_pipeline_yaml) -> None:
        """
        Tests that if a Pipeline instance has multiple previous runs, the most recent
        run is loaded in last_run attribute at Pipeline creation.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is no stages_to_run parameters to warn the user that
            all stages will be run by default.
        """

        logs = tmp_path / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "onsrap.log").write_text(
            "2026-08-11 10:00:00,000 Pipeline started | "
            '{"run_id": "run_older", '
            '"name": "test_pipeline", '
            ' "run_dir": "/path/to/run"}\n'
            "2026-08-11 10:01:00,000 Pipeline started | "
            '{"run_id": "run_newer", '
            '"name": "test_pipeline", '
            ' "run_dir": "/path/to/run"}'
        )

        temp_attributes_1 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_older"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_1.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_1.write_text(
            minimal_pipeline_yaml(run_id="run_older"), encoding="utf-8"
        )

        temp_attributes_2 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_newer"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_2.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_2.write_text(
            minimal_pipeline_yaml(run_id="run_newer"), encoding="utf-8"
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs", log_dir=logs),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline.last_run is not None
        assert pipeline.last_run.manifest.run_id == "run_newer"

    def test_last_run_most_recent_no_directory(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Checks that only the older run is included when the run directory has been
        deleted/removed for the most recent run.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is no stages_to_run parameters to warn the user that
            all stages will be run by default.
        """

        logs = tmp_path / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "onsrap.log").write_text(
            "2026-08-11 10:00:00,000 Pipeline started | "
            '{"name": "test_pipeline", "run_id": "run_older", '
            ' "run_dir": "/path/to/run"}\n'
            "2026-08-11 10:01:00,000 Pipeline started | "
            '{"name": "test_pipeline", "run_id": "run_newer", '
            ' "run_dir": "/path/to/run"}'
        )

        temp_attributes_1 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_older"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_1.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_1.write_text(
            minimal_pipeline_yaml(run_id="run_older"), encoding="utf-8"
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs", log_dir=logs),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline.last_run is not None
        assert pipeline.last_run.manifest.run_id == "run_older"


class TestLoadAllRunsUnitTests(TestLoadLatestRunIntegration):
    def test_returns_none_when_error_in_extract_historical_runs(
        self, monkeypatch, pipeline_no_history
    ) -> None:
        """
        Checks that all_runs attribute is None when extract_historical_run_ids
        raises an error. This is to ensure that the Pipeline instance does not break
        when there is an issue with extracting historical runs.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is an issue with extracting historical runs, indicating
            that the all_runs attribute will be None.
        """

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            mock.Mock(side_effect=HistoricalPipelineLoadError("test")),
        )

        with pytest.warns(PipelineConfigurationWarning):
            assert pipeline_no_history._load_all_runs() is None
            assert pipeline_no_history.all_runs is None

    def test_returns_none_when_blank_extract_historical_runs(
        self, monkeypatch, pipeline_no_history
    ) -> None:
        """
        Checks that all_runs attribute is None when extract_historical_run_ids
        returns a blank list. This ensures that the Pipeline instance does not
        break when there are no historical runs.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there are no historical runs found, indicating that the
            all_runs attribute will be None.
        """
        monkeypatch.setattr(
            pipeline_no_history.logger, "extract_historical_run_ids", lambda x, y: []
        )

        assert (
            pipeline_no_history.logger.extract_historical_run_ids(
                pipeline_no_history.run_output, pipeline_no_history.name
            )
            == []
        )
        with pytest.warns(PipelineConfigurationWarning):
            assert pipeline_no_history._load_all_runs() is None
            assert pipeline_no_history.all_runs is None

    def test_single_entry_dict_single_run(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Checks that all_runs attribute is a dictionary with a single entry when
        extract_historical_run_ids returns a list with one historical run. This
        ensures that the Pipeline instance correctly loads a single historical run.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is one historical run found, indicating that the
            all_runs attribute will contain a single entry.
        """

        mock_loader = mock.MagicMock(return_value=mock.sentinel)
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "run_A",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                }
            ],
        )

        result = pipeline_no_history._load_all_runs()
        assert isinstance(result, dict)
        assert len(result) == 1
        assert "run_A" in result
        mock_loader.assert_called_once_with(
            run_dir=FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_A"
        )

    def test_multiple_entries_dict_multiple_runs(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Checks that all_runs attribute is a dictionary with multiple entries when
        extract_historical_run_ids returns a list with multiple historical runs.
        This ensures that the Pipeline instance correctly loads multiple historical runs.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there are multiple historical runs found, indicating that the
            all_runs attribute will contain multiple entries.
        """

        mock_loader = mock.MagicMock(
            side_effect=[mock.sentinel.run_A, mock.sentinel.run_B]
        )
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "run_A",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": "run_B",
                    "timestamp": "2026-08-10 10:01:00,000",
                    "run_dir": Path("/path/to/run_B"),
                },
            ],
        )

        result = pipeline_no_history._load_all_runs()
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "run_A" in result and "run_B" in result
        mock_loader.assert_any_call(
            run_dir=FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_A"
        )
        mock_loader.assert_any_call(
            run_dir=FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_B"
        )

    def test_warning_if_no_run_id(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Checks that a warning is raised if extract_historical_run_ids returns a
        historical run without a run_id. This ensures that the Pipeline instance
        correctly handles cases where historical runs are missing identifiers.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.
        """
        mock_loader = mock.MagicMock(return_value=mock.sentinel)
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": "run_B",
                    "timestamp": "2026-08-10 10:01:00,000",
                    "run_dir": Path("/path/to/run_B"),
                },
                {
                    "run_id": None,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
            ],
        )

        with pytest.warns(PipelineConfigurationWarning):
            result = pipeline_no_history._load_all_runs()
        assert isinstance(result, dict)
        assert len(result) == 1
        assert "run_A" not in result and "run_B" in result
        mock_loader.assert_called_once_with(
            run_dir=FileSystemSetUp.confirm_typing(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_B"
        )

    def test_None_with_stageloaderror(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Checks that all_runs attribute is None when load_historical_run raises a
        StageLoadError. This ensures that the Pipeline instance correctly handles
        cases where historical runs cannot be loaded due to errors.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is an issue loading a historical run, indicating that
            the all_runs attribute will be None.
        """

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "good_run",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": "bad_run",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_B"),
                },
            ],
        )

        monkeypatch.setattr(
            "onsrap.pipeline.load_historical_run",
            mock.Mock(side_effect=[mock.sentinel.good_run, StageLoadError("test")]),
        )

        with pytest.warns(PipelineConfigurationWarning):
            result = pipeline_no_history._load_all_runs()
            assert isinstance(result, dict)
            assert len(result) == 1
            assert "good_run" in result and "bad_run" not in result

    def test_none_if_all_stageloaderrors(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Asserts that all_runs attribute is None when load_historical_run raises a
        StageLoadError for all historical runs. This ensures that the Pipeline instance
        correctly handles cases where all historical runs cannot be loaded due to errors.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is an issue loading all historical runs, indicating that
            the all_runs attribute will be None.
        """

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "bad_run1",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": "bad_run2",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_B"),
                },
            ],
        )

        monkeypatch.setattr(
            "onsrap.pipeline.load_historical_run",
            mock.Mock(side_effect=[StageLoadError("test"), StageLoadError("test")]),
        )

        with pytest.warns(PipelineConfigurationWarning):
            result = pipeline_no_history._load_all_runs()

        assert result is None
        assert pipeline_no_history.all_runs is None

    def test_success_run_no_errors(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Asserts that the pipeline correctly loads all historical runs without errors.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised if there is an issue loading historical runs, which should not
            happen in this test.
        """
        mock_loader = mock.MagicMock(
            side_effect=[mock.sentinel.run_A, mock.sentinel.run_B]
        )
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "run_A",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": "run_B",
                    "timestamp": "2026-08-10 10:01:00,000",
                    "run_dir": Path("/path/to/run_B"),
                },
            ],
        )

        with warnings.catch_warnings(record=True) as w:
            result = pipeline_no_history._load_all_runs()

        assert not any(
            issubclass(warning.category, PipelineConfigurationWarning) for warning in w
        )
        assert result == {"run_A": mock.sentinel.run_A, "run_B": mock.sentinel.run_B}
        assert mock_loader.call_count == 2

    def test_all_log_entries_invalid_ids(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Asserts that the pipeline returns None for all_runs when all historical
        runs have an invalid run_id (either empty or None).

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when all historical runs have invalid run_ids, indicating that
            the all_runs attribute will be None.
        """
        mock_loader = mock.MagicMock(return_value=mock.sentinel)
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
                {
                    "run_id": None,
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run_A"),
                },
            ],
        )

        with pytest.warns(PipelineConfigurationWarning):
            result = pipeline_no_history._load_all_runs()
        assert result is None
        assert pipeline_no_history.all_runs is None

    def test_duplicate_run_ids_overwrite(
        self, monkeypatch, pipeline_no_history: Pipeline
    ) -> None:
        """
        Asserts that when duplicate run_ids are found, the last one in the list
        overwrites the previous one in the all_runs dictionary.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for dynamic modification of attributes,
            methods, or classes during testing.
        ``pipeline_no_history`` : Pipeline
            A Pipeline instance with no historical runs.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when duplicate run_ids are found, indicating that the last one
            will overwrite the previous one in the all_runs dictionary.
        """
        mock_loader = mock.MagicMock(
            side_effect=[mock.sentinel.first_loaded, mock.sentinel.second_loaded]
        )
        monkeypatch.setattr("onsrap.pipeline.load_historical_run", mock_loader)

        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "run_A",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/first_loaded"),
                },
                {
                    "run_id": "run_A",
                    "timestamp": "2026-08-10 10:01:00,000",
                    "run_dir": Path("/path/to/second_loaded"),
                },
            ],
        )

        with warnings.catch_warnings(record=True) as w:
            result = pipeline_no_history._load_all_runs()

        assert not any(
            issubclass(warning.category, PipelineConfigurationWarning) for warning in w
        )

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 1
        assert result["run_A"] is mock.sentinel.second_loaded


class TestLoadAllRunsIntegration(TestLoadLatestRunIntegration):
    def test_all_runs_none_first_run(self, tmp_path: Path) -> None:
        """
        Tests that when a Pipeline instance has no previous runs, the all_runs
        attribute is None.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when no previous runs are found for the Pipeline, indicating
            that the all_runs attribute will be None.
        """

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )
        pipeline.run_output = tmp_path / "runs"
        assert pipeline.all_runs is None

    def test_all_runs_populated_multiple_runs(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Tests that when a Pipeline instance has multiple previous runs, the all_runs
        attribute is populated with all historical runs.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.
        """

        logs = tmp_path / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "onsrap.log").write_text(
            "2026-08-11 10:00:00,000 Pipeline started | "
            '{"run_id": "run_older", '
            ' "name": "test_pipeline",'
            ' "run_dir": "/path/to/run"}\n'
            "2026-08-11 10:01:00,000 Pipeline started | "
            '{"run_id": "run_newer", '
            ' "name": "test_pipeline",'
            ' "run_dir": "/path/to/run"}'
        )

        temp_attributes_1 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_older"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_1.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_1.write_text(
            minimal_pipeline_yaml(run_id="run_older"), encoding="utf-8"
        )

        temp_attributes_2 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_newer"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_2.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_2.write_text(
            minimal_pipeline_yaml(run_id="run_newer"), encoding="utf-8"
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs", log_dir=logs),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline.all_runs is not None
        assert pipeline.all_runs["run_newer"].manifest.run_id == "run_newer"
        assert pipeline.all_runs["run_older"].manifest.run_id == "run_older"
        assert len(pipeline.all_runs) == 2

    def test_deleted_run_not_populated_all_runs(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Tests that when a Pipeline instance has multiple previous runs but one of those
        runs have been deleted/removed, the all_runs attribute is populated only
        with the existing historical runs.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.

        Raises
        ------
        ``PipelineConfigurationWarning``
            Raised when there is no stages_to_run parameters to warn the user that
            all stages will be run by default.
        """

        logs = tmp_path / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "onsrap.log").write_text(
            "2026-08-11 10:00:00,000 Pipeline started | "
            '{"run_id": "run_older", '
            '"name": "test_pipeline",'
            ' "run_dir": "/path/to/run"}\n'
            "2026-08-11 10:01:00,000 Pipeline started | "
            '{"run_id": "run_newer", '
            '"name": "test_pipeline",'
            ' "run_dir": "/path/to/run"}'
        )

        temp_attributes_1 = (
            tmp_path
            / "outputs"
            / "runs"
            / "run_older"
            / "pipeline_attributes_for_test.yaml"
        )
        temp_attributes_1.parent.mkdir(parents=True, exist_ok=True)
        temp_attributes_1.write_text(
            minimal_pipeline_yaml(run_id="run_older"), encoding="utf-8"
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="test_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs", log_dir=logs),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline.all_runs is not None
        assert pipeline.all_runs["run_older"].manifest.run_id == "run_older"
        assert len(pipeline.all_runs) == 1
