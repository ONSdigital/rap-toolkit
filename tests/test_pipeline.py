import warnings
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from rap_toolkit.errors import (
    HistoricalPipelineLoadError,
    PipelineConfigurationError,
    PipelineInitialisationError,
    StageConfigurationError,
    StageLoadError,
)
from rap_toolkit.execution import PythonStageExecutor
from rap_toolkit.file_system_setup import FileSystemSetUp
from rap_toolkit.models import PipelineRun, StageConfig
from rap_toolkit.pipeline import Pipeline, PipelineConfig
from rap_toolkit.stage import Stage
from rap_toolkit.warnings import PipelineConfigurationWarning, StageConfigurationWarning

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
                name="test pipeline name",
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

    def test_init_rejects_constructor_stages_and_config_defined_stages(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Tests that when a Pipeline is initialised with both stages defined in the
        constructor and in the configuration, a PipelineInitialisationError is raised.
        """
        configured_stage = tmp_path / "configured_stage.py"
        configured_stage.write_text(
            "def run(context):\n    return 'ok'\n", encoding="utf-8"
        )

        config = {
            "pipeline_variables": {
                "work_dir": tmp_path,
                "project_root": tmp_path,
                "log_dir": tmp_path / "logs",
                "stages": [
                    {
                        "configured_stage": {
                            "location": str(configured_stage),
                        }
                    }
                ],
            },
            "stage_configuration": {},
        }

        with pytest.raises(PipelineInitialisationError):
            Pipeline(config=config, stages=[stage_factory("Stage_0")])

    def test_init_rejects_backend_mismatch_between_argument_and_config(
        self,
    ) -> None:
        """
        Tests that when a Pipeline is initialised with a backend argument that
        mismatches the backend specified in the configuration, a
        PipelineInitialisationError is raised.
        """
        with pytest.raises(PipelineInitialisationError):
            Pipeline(
                backend="python",
                config=PipelineConfig(backend="spark"),
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
            )

    def test_init_uses_supplied_executor_without_generating_context(
        self, monkeypatch
    ) -> None:
        """
        Test that checks that an execution context is not generated if one is already
        supplied to the Pipeline creation.
        """
        generate_context = mock.Mock()
        monkeypatch.setattr(Pipeline, "_generate_context", generate_context)
        executor = mock.Mock()

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[Stage("Stage_0", source=Path("Stage_0.py"), dependencies=())],
                executor=executor,
            )

        assert pipeline.executor is executor
        generate_context.assert_not_called()

    def test_from_files_rejects_non_path_non_string_entries(self) -> None:
        """
        Checks error detection in from_files method to ensure that the files listed
        are either Path objects or strings.
        """
        with pytest.raises(PipelineConfigurationError):
            Pipeline.from_files([123])

    def test_assign_dependencies_single_stage_tuple_form(self, stage_factory) -> None:
        """
        Checks that multiple dependencies can be assigned to a single stage as a tuple.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        stage = pipeline.stages[0]
        assigned = pipeline._assign_dependencies(("dep_a", "dep_b"), stage)

        assert assigned == {"Stage_0": ("dep_a", "dep_b")}
        assert stage.dependencies == ("dep_a", "dep_b")

    def test_normalize_dependency_values_deduplicates_and_strips_blanks(self) -> None:
        """
        Checks that the pipeline normalization method appropriately handles duplicates,
        white space, and blanks.
        """
        assert Pipeline._normalize_dependency_values(
            ["dep_a", " ", "dep_a", "dep_b"]
        ) == (
            "dep_a",
            "dep_b",
        )

    def test_normalize_dependency_values_deduplicates_with_white_space(self) -> None:
        """
        Checks that the pipeline normalization method appropriately handles duplicates,
        even if one contains white space.
        """
        assert Pipeline._normalize_dependency_values(["dep_a", "dep_a ", "dep_b"]) == (
            "dep_a",
            "dep_b",
        )

    def test_normalize_dependency_mapping_converts_values_to_tuples(self) -> None:
        """
        Checks that dependnecies assigned as lists are appropriately converted to tuples.
        """
        normalized = Pipeline._normalize_dependency_mapping(
            {"Stage_0": ["dep_a", "dep_a"], "Stage_1": "dep_b"}
        )

        assert normalized == {
            "Stage_0": ("dep_a",),
            "Stage_1": ("dep_b",),
        }

    def test_dependencies_for_stage_matches_callable_name(self) -> None:
        """
        Tests that when dependencies for a specific stage are requested, they
        are returned in an appropriate format.
        """

        def callable_stage():
            return None

        result = Pipeline._dependencies_for_stage(
            "Stage_0", callable_stage, {"callable_stage": ["dep_a"]}
        )

        assert result == ("dep_a",)


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

    def test_create_stage_config_selects_named_stage_from_composite_mapping(
        self, stage_factory
    ) -> None:
        """
        Tests that the create_stage_config method correctly selects the named
        stage from a composite mapping of stage configurations.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_factory("Stage_0"), stage_factory("Stage_1")]
            )

        result = pipeline.create_stage_config(
            {
                "Stage_0": {"years_to_run": 2017},
                "Stage_1": {"years_to_run": 2018},
            },
            name="Stage_1",
        )

        assert result.name == "Stage_1"
        assert result.require("years_to_run") == 2018

    def test_create_stage_config_errors_when_multiple_stage_configs_and_no_name(
        self, stage_factory
    ) -> None:
        """
        Tests that the create_stage_config method raises an error when
        multiple stage configurations are provided and no stage name is specified.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_factory("Stage_0"), stage_factory("Stage_1")]
            )

        with pytest.raises(
            StageConfigurationError, match="multiple stage configurations"
        ):
            pipeline.create_stage_config(
                {
                    "Stage_0": {"years_to_run": 2017},
                    "Stage_1": {"years_to_run": 2018},
                }
            )

    def test_create_stage_config_errors_when_named_stage_missing_from_composite_mapping(
        self, stage_factory
    ) -> None:
        """
        Tests that the create_stage_config method raises an error when
        the named stage is missing from a composite mapping of stage configurations.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(StageConfigurationError, match="was not found"):
            pipeline.create_stage_config(
                {"Stage_1": {"years_to_run": 2017}},
                name="Stage_0",
            )

    def test_add_stage_config_rejects_stageconfig_name_mismatch(
        self, stage_factory
    ) -> None:
        """
        Tests that the add_stage_config method raises an error when
        the stage configuration name does not match the specified stage name to prevent
        stage configurations being added to the incorrect stages.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(StageConfigurationError, match="does not match stage"):
            pipeline.add_stage_config(
                StageConfig(name="Stage_1", _variables={"years_to_run": 2017}),
                name="Stage_0",
            )

    def test_add_stage_config_accepts_named_mapping_payload_with_scalar_values(
        self, stage_factory
    ) -> None:
        """
        Tests that the add_stage_config method accepts a named mapping payload
        with scalar values.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        pipeline.add_stage_config({"Stage_0": "not-a-mapping"}, name="Stage_0")

        assert pipeline.stage_configs["Stage_0"].to_dict() == {
            "Stage_0": "not-a-mapping"
        }

    def test_create_stage_config_rejects_unsupported_payload_type(
        self, stage_factory
    ) -> None:
        """
        Tests that the create_stage_config method raises an error when
        an unsupported payload type is provided such as an integer.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(
            StageConfigurationError,
            match="Unsupported stage configuration specification",
        ):
            pipeline.create_stage_config(123)

    def test_resolve_config_warns_for_stage_configuration_in_pipelineconfig_metadata(
        self, stage_factory
    ) -> None:
        """
        Tests that the resolve_config method warns when a stage configuration
        is found in the PipelineConfig metadata.
        """
        config = PipelineConfig(
            output_dir=Path("outputs"),
            metadata={"stage_configuration": {"Stage_0": {"years_to_run": 2017}}},
        )

        with pytest.warns(
            (PipelineConfigurationWarning, StageConfigurationWarning)
        ) as warnings:
            pipeline = Pipeline(config=config, stages=[stage_factory("Stage_0")])

        assert any(
            "Stage configuration found in PipelineConfig metadata"
            in str(warning.message)
            for warning in warnings
        )

        assert pipeline.stage_configs["Stage_0"].require("years_to_run") == 2017

    def test_resolve_config_warns_for_global_configuration_in_pipelineconfig_metadata(
        self, stage_factory
    ) -> None:
        """
        Tests that the resolve_config method warns when a global configuration
        is found in the PipelineConfig metadata.
        """
        config = PipelineConfig(
            output_dir=Path("outputs"),
            metadata={"global_config": {"dry_run": True}},
        )

        with pytest.warns(
            (StageConfigurationWarning, PipelineConfigurationWarning)
        ) as warnings:
            pipeline = Pipeline(config=config, stages=[stage_factory("Stage_0")])

        assert any(
            "Global configuration found in PipelineConfig metadata"
            in str(warning.message)
            for warning in warnings
        )

        global_variables, exclusions = pipeline.global_config.get_attributes()
        assert global_variables["dry_run"] is True
        assert exclusions == {}


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

    def test_resolve_stages_to_run_rejects_unknown_stage_names(
        self, stage_factory
    ) -> None:
        """
        Tests that the resolve_stages_to_run method raises an error when
        unknown stage names are provided.
        """
        with pytest.raises(PipelineInitialisationError, match="unknown stages"):
            Pipeline(
                stages=[stage_factory("Stage_0")],
                config=PipelineConfig(stages_to_run={"Missing": True}),
            )

    def test_resolve_stages_to_run_returns_empty_graph_when_all_disabled(
        self, stage_factory
    ) -> None:
        """
        Tests that the resolve_stages_to_run method returns an empty graph when
        all stages are disabled.
        """
        with pytest.warns((StageConfigurationWarning, PipelineConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_factory("Stage_0"), stage_factory("Stage_1")],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": False, "Stage_1": False}
                ),
            )

        assert pipeline.graph.stages == []
        assert pipeline.ordered_stages() == []

    def test_enable_stage_raises_for_unknown_stage(self, stage_factory) -> None:
        """
        Tests that the enable_stage method raises an error when an unknown stage is specified.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(PipelineInitialisationError, match="does not exist"):
            pipeline.enable_stage("Missing")

    def test_disable_stage_raises_for_unknown_stage(self, stage_factory) -> None:
        """
        Tests that the disable_stage method raises an error when an unknown stage is specified.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(PipelineInitialisationError, match="does not exist"):
            pipeline.disable_stage("Missing")

    def test_enable_stage_flattens_list_arguments(self, stage_factory) -> None:
        """
        Tests that the enable_stage method correctly flattens list arguments.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_factory("Stage_0"), stage_factory("Stage_1")],
                config=PipelineConfig(
                    stages_to_run={"Stage_0": False, "Stage_1": False}
                ),
            )

        pipeline.enable_stage(["Stage_0", "Stage_1"])

        assert pipeline.config.stages_to_run == {"Stage_0": True, "Stage_1": True}
        assert {stage.name for stage in pipeline.graph.stages} == {"Stage_0", "Stage_1"}

    def test_disable_stage_flattens_list_arguments(self, stage_factory) -> None:
        """
        Tests that the disable_stage method correctly flattens list arguments.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                stages=[stage_factory("Stage_0"), stage_factory("Stage_1")]
            )

        pipeline.disable_stage(["Stage_0", "Stage_1"])

        assert pipeline.config.stages_to_run == {"Stage_0": False, "Stage_1": False}
        assert pipeline.graph.stages == []

    def test_add_stage_rejects_stage_config_for_unknown_stage(
        self, stage_factory
    ) -> None:
        """
        Tests that the add_stage method raises an error when a stage config is provided for an unknown stage.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        with pytest.raises(StageConfigurationError, match="was not found"):
            pipeline.add_stage(
                stage_factory("Stage_1"),
                stage_configs=[{"DifferentStage": {"years_to_run": 2017}}],
            )

    def test_add_stage_with_no_stages_warns_and_changes_nothing(
        self, stage_factory
    ) -> None:
        """
        Tests that the add_stage method warns and changes nothing when no stages are provided.
        """
        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(stages=[stage_factory("Stage_0")])

        original_stages = list(pipeline.stages)
        original_stage_configs = dict(pipeline.stage_configs)

        with pytest.warns(PipelineConfigurationWarning, match="No stages provided"):
            pipeline.add_stage()

        assert pipeline.stages == original_stages
        assert pipeline.stage_configs == original_stage_configs
        assert [stage.name for stage in pipeline.graph.stages] == ["Stage_0"]


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

    def test_validate_raises_when_stage_output_directory_exists_and_overwrite_false(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Test that the validate method raises an error if the stage output directory
        already exists and the pipeline is configured not to overwrite it.
        """
        existing_output_dir = tmp_path / "existing_output"
        existing_output_dir.mkdir()
        stage_file = tmp_path / "Stage_0.py"
        stage_file.write_text("def run(context):\n    return None\n", encoding="utf-8")

        with pytest.warns((PipelineConfigurationWarning, StageConfigurationWarning)):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs", overwrite=False),
                stages=[stage_factory("Stage_0", source=stage_file)],
            )

        with pytest.warns(StageConfigurationWarning):
            pipeline.add_stage_config(
                {"output_dir": str(existing_output_dir)}, name="Stage_0"
            )

            with pytest.raises(StageConfigurationError, match="already exists"):
                pipeline.validate()

    def test_validate_warns_when_stage_output_directory_exists_and_overwrite_true(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Test that the validate method warns if the stage output directory
        already exists and the pipeline is configured to overwrite it.
        """
        existing_output_dir = tmp_path / "existing_output"
        existing_output_dir.mkdir()
        stage_file = tmp_path / "Stage_0.py"
        stage_file.write_text("def run(context):\n    return None\n", encoding="utf-8")

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs", overwrite=True),
                stages=[stage_factory("Stage_0", source=stage_file)],
            )

        with pytest.warns(StageConfigurationWarning):
            pipeline.add_stage_config(
                {"output_dir": str(existing_output_dir)}, name="Stage_0"
            )

        with pytest.warns(StageConfigurationWarning) as recorded_warnings:
            pipeline.validate()

        assert any("overwrite" in str(record.message) for record in recorded_warnings)

    def test_add_stage_config_warns_when_output_directory_keys_present(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Test that the add_stage_config method warns when output directory keys are present.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[stage_factory("Stage_0")],
            )

        with pytest.warns(
            StageConfigurationWarning, match="contains output directory keys"
        ):
            pipeline.add_stage_config({"output_dir": "artifact"}, name="Stage_0")

    def test_manifest_parameters_includes_stage_configuration_when_present(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Test that the manifest parameters include the stage configuration when present.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[stage_factory("Stage_0")],
            )

        pipeline.add_stage_config({"years_to_run": 2017}, name="Stage_0")
        parameters = pipeline._manifest_parameters()

        assert parameters["stage_configuration"]["Stage_0"]["years_to_run"] == 2017

    def test_combine_configs_returns_pipeline_stage_and_global_sections(
        self, tmp_path: Path, stage_factory
    ) -> None:
        """
        Test that the _combine_configs method returns the pipeline, stage, and global sections.
        """
        config = {
            "pipeline_config": {
                "output_dir": tmp_path / "outputs",
                "work_dir": tmp_path,
                "project_root": tmp_path,
                "log_dir": tmp_path / "logs",
            },
            "stage_configuration": {"Stage_0": {"years_to_run": 2017}},
            "global_config": {"dry_run": True},
        }

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(config=config, stages=[stage_factory("Stage_0")])

        combined = pipeline._combine_configs()

        assert set(combined) == {"pipeline_config", "stage_configs", "global_config"}
        assert combined["stage_configs"]["Stage_0"]["years_to_run"] == 2017
        assert combined["global_config"]["dry_run"] is True

    def test_create_runtime_id_contains_timestamp_hash_and_short_hash_consistently(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _create_runtime_id method generates a runtime ID containing
        a timestamp, a hash, and a short hash consistently.
        """
        fixed_now = datetime(2026, 10, 7, 12, 34, 56)
        monkeypatch.setattr("rap_toolkit.pipeline.now", lambda: fixed_now)

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        runtime_id = pipeline._create_runtime_id()

        assert runtime_id.timestamp == fixed_now
        assert runtime_id.short_hash == runtime_id.hash[:8]
        assert runtime_id.id == f"2026-10-07_123456_{runtime_id.short_hash}"

    def test_discover_git_commit_returns_none_on_oserror(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _discover_git_commit method returns None when an OSError is raised.
        """
        monkeypatch.setattr(
            "rap_toolkit.pipeline.subprocess.run", mock.Mock(side_effect=OSError())
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline._discover_git_commit() is None

    def test_discover_git_commit_returns_none_on_blank_stdout(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _discover_git_commit method returns None when the stdout is blank.
        """
        monkeypatch.setattr(
            "rap_toolkit.pipeline.subprocess.run",
            mock.Mock(return_value=mock.Mock(stdout="   ")),
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline._discover_git_commit() is None

    def test_package_versions_includes_python_when_pyyaml_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _package_versions method includes Python when PyYAML is missing.
        """
        package_not_found = type("PackageNotFoundError", (Exception,), {})
        monkeypatch.setattr(
            "rap_toolkit.pipeline.importlib_metadata.PackageNotFoundError",
            package_not_found,
        )
        monkeypatch.setattr(
            "rap_toolkit.pipeline.importlib_metadata.version",
            mock.Mock(side_effect=package_not_found()),
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        versions = pipeline._package_versions()

        assert any(version.startswith("python=") for version in versions)
        assert not any(version.startswith("pyyaml=") for version in versions)

    def test_current_user_returns_none_when_getuser_raises(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _current_user method returns None when getuser raises a RuntimeError.
        """
        monkeypatch.setattr(
            "rap_toolkit.pipeline.getpass.getuser",
            mock.Mock(side_effect=RuntimeError()),
        )

        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        assert pipeline._current_user() is None

    def test_pipeline_str_includes_core_attributes(self, tmp_path: Path) -> None:
        """
        Checks that correct attributes are included in the string representation of the Pipeline instance.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="example_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        text = str(pipeline)

        assert "Pipeline Instance Attributes" in text
        assert "example_pipeline" in text
        assert "Backend:" in text
        assert "Executor:" in text

    def test_pipeline_repr_includes_core_attributes(self, tmp_path: Path) -> None:
        """
        Test that the repr of the Pipeline instance includes core attributes.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                name="example_pipeline",
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        text = repr(pipeline)

        assert "Pipeline(name=example_pipeline" in text
        assert "backend=python" in text
        assert "stages=" in text


class TestPipelineCompositeConfigurationHelpers:
    def test_load_config_mapping_rejects_unsupported_suffix(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _load_config_mapping method rejects unsupported file suffixes.
        """
        config_file = tmp_path / "conf.txt"
        config_file.write_text("pipeline_config: {}\n", encoding="utf-8")

        with pytest.raises(
            StageConfigurationError, match="Unsupported config file format"
        ):
            Pipeline._load_config_mapping(config_file)

    def test_load_config_mapping_raises_for_missing_file(self, tmp_path: Path) -> None:
        """
        Test that the _load_config_mapping method raises a FileNotFoundError for a missing file.
        """
        with pytest.raises(FileNotFoundError, match="Config file does not exist"):
            Pipeline._load_config_mapping(tmp_path / "missing.yaml")

    def test_load_config_mapping_returns_empty_dict_for_blank_yaml(
        self, tmp_path: Path
    ) -> None:
        """
        Tests that a warning is raised and a blank configuration is received
        when the configuration file is empty.
        """
        config_file = tmp_path / "blank.yaml"
        config_file.write_text("", encoding="utf-8")

        with pytest.warns(UserWarning, match="No configuration has loaded"):
            result = Pipeline._load_config_mapping(config_file)

        assert result == {}

    def test_load_config_mapping_rejects_non_mapping_top_level_yaml(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _load_config_mapping method rejects non-mapping top-level YAML content.
        """
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- a\n- b\n", encoding="utf-8")

        with pytest.raises(
            TypeError, match="Configuration file must contain a mapping"
        ):
            Pipeline._load_config_mapping(config_file)

    def test_split_config_sections_raises_when_required_pipeline_key_missing(
        self,
    ) -> None:
        """
        Test that the _split_config_sections method raises a PipelineConfigurationError
        when the required pipeline key is missing.
        """
        with pytest.raises(
            PipelineConfigurationError, match="No valid keys were found"
        ):
            Pipeline._split_config_sections({"stage_configuration": {}})

    def test_split_config_sections_warns_when_multiple_pipeline_aliases_present(
        self,
    ) -> None:
        """
        Test that the _split_config_sections method warns when multiple pipeline aliases are present.
        """
        raw_config = {
            "pipeline_variables": {"name": "first"},
            "pipeline_config": {"name": "second"},
            "stage_configuration": {},
        }

        with pytest.warns(
            (PipelineConfigurationWarning, StageConfigurationWarning)
        ) as warnings:
            pipeline_payload, stage_payload, global_payload = (
                Pipeline._split_config_sections(raw_config)
            )

        assert any(
            "Multiple configuration keys were found" in str(warning.message)
            for warning in warnings
        )
        assert pipeline_payload == {"name": "first"}
        assert stage_payload == {}
        assert global_payload == {}

    def test_split_config_sections_warns_when_multiple_optional_alias_keys_present(
        self,
    ) -> None:
        """
        Test that the _split_config_sections method warns when multiple optional alias keys are present.
        """
        raw_config = {
            "pipeline_config": {"name": "pipeline"},
            "stage_configuration": {"Stage_0": {}},
            "stage_config": {"Stage_1": {}},
        }

        with pytest.warns(PipelineConfigurationWarning) as warnings:
            _, stage_payload, _ = Pipeline._split_config_sections(raw_config)
        assert any(
            "Multiple configuration keys were found" in str(warning.message)
            for warning in warnings
        )
        assert stage_payload == {"Stage_0": {}}

    def test_split_config_sections_warns_when_unextracted_sections_remain(self) -> None:
        """
        Test that the _split_config_sections method warns when unextracted sections remain.
        """
        raw_config = {
            "pipeline_config": {"name": "pipeline"},
            "stage_configuration": {},
            "unexpected": {"value": 1},
        }

        with pytest.warns(PipelineConfigurationWarning, match="remaining sections"):
            pipeline_payload, stage_payload, global_payload = (
                Pipeline._split_config_sections(raw_config)
            )

        assert pipeline_payload == {"name": "pipeline"}
        assert stage_payload == {}
        assert global_payload == {}

    def test_split_config_sections_rejects_non_mapping_pipeline_section(self) -> None:
        """
        Test that the _split_config_sections method rejects non-mapping pipeline section.
        """
        with pytest.raises(
            PipelineConfigurationError,
            match="pipeline_config section must be a mapping",
        ):
            Pipeline._split_config_sections(
                {"pipeline_config": ["bad"], "stage_configuration": {}}
            )

    def test_split_config_sections_rejects_non_mapping_stage_section(self) -> None:
        """
        Test that the _split_config_sections method rejects non-mapping stage section.
        """
        with pytest.raises(
            PipelineConfigurationError,
            match="stage_configuration section must be a mapping",
        ):
            Pipeline._split_config_sections(
                {"pipeline_config": {}, "stage_configuration": ["bad"]}
            )

    def test_split_config_sections_rejects_non_mapping_global_section(self) -> None:
        """
        Test that _split_config_sections reject non-mapping global section.
        """
        with pytest.raises(
            PipelineConfigurationError, match="global_config section must be a mapping"
        ):
            Pipeline._split_config_sections(
                {"pipeline_config": {}, "global_config": ["bad"]}
            )

    def test_normalize_pipeline_payload_maps_working_dir_alias(self) -> None:
        """
        Test that the _normalize_pipeline_payload method maps the working_dir alias to work_dir.
        """
        normalized = Pipeline._normalize_pipeline_payload({"working_dir": "tmp/work"})

        assert normalized == {"work_dir": "tmp/work"}

    def test_normalize_pipeline_payload_maps_stage_to_run_alias(self) -> None:
        """
        Test that the _normalize_pipeline_payload method maps the stage_to_run alias to stages_to_run.
        """
        normalized = Pipeline._normalize_pipeline_payload(
            {"stage_to_run": {"Stage_0": True}}
        )

        assert normalized == {"stages_to_run": {"Stage_0": True}}

    def test_normalize_pipeline_payload_warns_when_alias_and_canonical_keys_both_present(
        self,
    ) -> None:
        """
        Test that the _normalize_pipeline_payload method warns when both alias and canonical keys are present.
        """
        with pytest.warns(UserWarning) as recorded_warnings:
            normalized = Pipeline._normalize_pipeline_payload(
                {
                    "working_dir": "ignored",
                    "work_dir": "kept",
                    "stage_to_run": {"Stage_0": False},
                    "stages_to_run": {"Stage_0": True},
                }
            )

        assert len(recorded_warnings) == 2
        assert normalized["work_dir"] == "kept"
        assert normalized["stages_to_run"] == {"Stage_0": True}

    def test_stage_from_config_definition_rejects_invalid_non_mapping_entry(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _stage_from_config_definition method rejects invalid non-mapping entries.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")
        with pytest.raises(
            StageConfigurationError, match="Configured stage entries must be mappings"
        ):
            pipeline._stage_from_config_definition(
                123, backend="python", work_dir=work_dir
            )

    def test_stage_from_config_definition_rejects_multi_stage_compact_mapping(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _stage_from_config_definition method rejects multi-stage compact mappings.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")
        with pytest.raises(StageConfigurationError, match="exactly one stage name"):
            pipeline._stage_from_config_definition(
                {"Stage_0": {}, "Stage_1": {}}, backend="python", work_dir=work_dir
            )

    def test_stage_from_config_definition_rejects_non_mapping_stage_details(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _stage_from_config_definition method rejects non-mapping stage details.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")
        with pytest.raises(
            StageConfigurationError, match="must be provided as a mapping"
        ):
            pipeline._stage_from_config_definition(
                {"Stage_0": "bad"}, backend="python", work_dir=work_dir
            )

    def test_stage_from_config_definition_skips_stage_when_run_is_false(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _stage_from_config_definition method skips the stage when "run" is False.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")
        assert (
            pipeline._stage_from_config_definition(
                {"Stage_1": {"run": False, "location": "ignored.py"}},
                backend="python",
                work_dir=work_dir,
            )
            is None
        )

    def test_stage_from_config_definition_raises_when_source_location_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """
        Test that the _stage_from_config_definition method raises an error when the source location is missing.
        """
        with pytest.warns(PipelineConfigurationWarning):
            pipeline = Pipeline(
                config=PipelineConfig(output_dir=tmp_path / "outputs"),
                stages=[
                    Stage("Stage_0", source=tmp_path / "Stage_0.py", dependencies=())
                ],
            )

        monkeypatch.setattr(
            pipeline, "_resolve_stage_source", mock.Mock(return_value=None)
        )
        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")
        with pytest.raises(
            StageConfigurationError, match="has no source location defined"
        ):
            pipeline._stage_from_config_definition(
                {"Stage_1": {}}, backend="python", work_dir=work_dir
            )

    def test_resolve_stage_source_defaults_to_scripts_directory_when_location_blank(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _resolve_stage_source method defaults to the scripts directory when the location is blank.
        """
        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")

        result = Pipeline._resolve_stage_source("Stage_0", "", work_dir)

        assert str(result).endswith("/scripts/Stage_0.py")

    def test_resolve_stage_source_prefers_existing_explicit_candidate(
        self, tmp_path: Path
    ) -> None:
        """
        Test that the _resolve_stage_source method returns the appropriate location based on explicit
        parameters.
        """
        stage_file = tmp_path / "Stage_0.py"
        stage_file.write_text("def run(context):\n    return None\n", encoding="utf-8")
        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")

        result = Pipeline._resolve_stage_source("Stage_0", stage_file, work_dir)

        assert Path(result) == stage_file

    def test_resolve_stage_source_preserves_relative_suffix_for_candidate_paths(
        self, tmp_path: Path
    ) -> None:
        """
        Tests that _resolve_stage_source keeps prefix for the scripts.
        """
        scripts_dir = tmp_path / "custom_scripts"
        scripts_dir.mkdir()
        stage_file = scripts_dir / "special_stage.py"
        stage_file.write_text("def run(context):\n    return None\n", encoding="utf-8")
        work_dir = FileSystemSetUp.file_system_setup_factory(tmp_path, path_type="dir")

        result = Pipeline._resolve_stage_source(
            "special_stage", "custom_scripts/special_stage.py", work_dir
        )

        assert Path(result).parts[-2:] == ("custom_scripts", "special_stage.py")


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
    def test_returns_none_when_extract_historical_run_ids_raises(
        self, pipeline_no_history: Pipeline, monkeypatch
    ) -> None:
        """
        Tests that _load_latest_run returns None and raises a warning when extract_historical_run_ids raises HistoricalPipelineLoadError.
        """
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            mock.Mock(side_effect=HistoricalPipelineLoadError("test")),
        )

        with pytest.warns(
            PipelineConfigurationWarning,
            match="Unable to load previous runs for this Pipeline",
        ):
            assert pipeline_no_history._load_latest_run() is None

    def test_returns_none_when_latest_run_file_cannot_be_loaded(
        self, pipeline_no_history: Pipeline, monkeypatch
    ) -> None:
        """
        Tests that _load_latest_run returns None and raises a warning when the latest run file cannot be loaded.
        """
        monkeypatch.setattr(
            pipeline_no_history.logger,
            "extract_historical_run_ids",
            lambda x, y: [
                {
                    "run_id": "bad_run",
                    "timestamp": "2026-08-10 10:00:00,000",
                    "run_dir": Path("/path/to/run"),
                }
            ],
        )
        monkeypatch.setattr(
            "rap_toolkit.pipeline.load_historical_run",
            mock.Mock(side_effect=StageLoadError("test")),
        )

        with pytest.warns(
            PipelineConfigurationWarning,
            match="Historical run file does not exist",
        ):
            assert pipeline_no_history._load_latest_run() is None

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
            "rap_toolkit.pipeline.load_historical_run", mock_load_historical_run
        )

        result = pipeline_no_history._load_latest_run()

        assert result is expected_run

        expected_path = (
            FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir", ssl_file=None
            ).create_uri()
            + "/"
            + run_id
        )
        mock_load_historical_run.assert_called_once_with(
            run_dir=expected_path, ssl_file=None
        )

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
            "rap_toolkit.pipeline.load_historical_run", mock_load_historical_run
        )

        pipeline_no_history._load_latest_run()

        expected_path = (
            FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir", ssl_file=None
            ).create_uri()
            + "/"
            + str(run_id_1)
        )
        mock_load_historical_run.assert_called_once_with(
            run_dir=expected_path, ssl_file=None
        )

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
            "rap_toolkit.pipeline.load_historical_run", mock_load_historical_run
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
        (logs / "rap-toolkit.log").write_text(
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
        (logs / "rap-toolkit.log").write_text(
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
        (logs / "rap-toolkit.log").write_text(
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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
            run_dir=FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_A",
            ssl_file=None,
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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
            run_dir=FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_A",
            ssl_file=None,
        )
        mock_loader.assert_any_call(
            run_dir=FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_B",
            ssl_file=None,
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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
            run_dir=FileSystemSetUp.file_system_setup_factory(
                pipeline_no_history.run_output, path_type="dir"
            ).create_uri()
            + "/run_B",
            ssl_file=None,
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
            "rap_toolkit.pipeline.load_historical_run",
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
            "rap_toolkit.pipeline.load_historical_run",
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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
        monkeypatch.setattr("rap_toolkit.pipeline.load_historical_run", mock_loader)

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
        (logs / "rap-toolkit.log").write_text(
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
        (logs / "rap-toolkit.log").write_text(
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
