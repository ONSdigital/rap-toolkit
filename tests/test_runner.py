import argparse
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest
import yaml

from rap_toolkit.errors import StageExecutionError
from rap_toolkit.execution import ExecutionContext
from rap_toolkit.file_system_setup import FileSystemSetUp
from rap_toolkit.logger import Logger
from rap_toolkit.models import (
    GlobalConfig,
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    RunManifest,
    RuntimeID,
    StageConfig,
    StageResult,
    StageStatus,
    now,
)
from rap_toolkit.runner import _log_config, _log_pipeline_attributes, print_config_diffs
from rap_toolkit.stage import Stage


class TestLogConfig:
    def test_writes_manifest_config_as_block_style_yaml(self, tmp_path: Path) -> None:
        """
        Tests that the ``_log_config`` function correctly writes the manifest
        configuration to a YAML file in block style format.

        Parameters
        ----------
        tmp_path : Path
            A temporary directory provided by pytest for creating test files.
        """
        run_dir = tmp_path / "runs" / "synthetic_run"
        run_dir.mkdir(parents=True)

        run_dir = FileSystemSetUp.file_system_setup_factory(run_dir, path_type="dir")

        config = PipelineConfig(
            name="synthetic_pipeline",
            stages_to_run={"stage_a": True},
            backend="python",
            work_dir=tmp_path / "work",
            project_root=tmp_path,
            output_dir=tmp_path / "outputs",
            log_dir=tmp_path / "logs",
            data_dir=tmp_path / "data",
            allow_subprocess_fallback=True,
            python_executable=None,
            metadata={"reason": "unit test"},
        )

        context = ExecutionContext(
            pipeline_name="synthetic_pipeline",
            run_id="run_1234",
            config=config,
            logger=Logger(),
            run_dir=run_dir,
            working_directory=tmp_path,
            stage_configs={},
            global_config=None,
        )

        manifest_config = {
            "pipeline_config": {
                "name": "synthetic_pipeline",
                "backend": "python",
                "output_dir": str(tmp_path / "outputs"),
            },
            "stage_configs": {
                "stage_a": {
                    "years_to_run": 2026,
                    "target_variable": "classification",
                }
            },
            "global_config": {
                "dry_run": True,
            },
        }

        manifest = RunManifest(
            rap_name="synthetic_pipeline",
            run_id="run_1234",
            config=manifest_config,
        )

        _log_config(run_dir, context, manifest)

        config_file = FileSystemSetUp.file_system_setup_factory(
            run_dir, path_type="dir"
        )
        config_file.file_name = (
            "configuration_for_"
            f"{context.pipeline_name}_{context.started_at.date()}_"
            f"{context.run_id[-8:]}.yaml"
        )

        expected_file = config_file.create_path()

        assert expected_file is not None
        assert expected_file.exists()

        file_text = expected_file.read_text(encoding="utf-8")
        parsed_yaml = yaml.safe_load(file_text)

        assert parsed_yaml == manifest_config
        assert "stage_configs:\n" in file_text
        assert "  stage_a:\n" in file_text
        assert "    years_to_run: 2026\n" in file_text
        assert "pipeline_config: {" not in file_text
        assert "stage_configs: {" not in file_text
        assert "global_config: {" not in file_text


class TestPrintConfigDiffs:
    @staticmethod
    def _write_yaml(path: Path, content: str) -> None:
        """
        Helper function that writes a YAML file to the specified path with
        the provided content. The content is dedented and stripped of
        leading/trailing whitespace before being written to the file. A newline is
        added at the end of the file.

        Parameters
        ----------
        ``path`` : Path
            The path where the YAML file will be written.
        ``content`` : str
            The YAML content to write to the file.
        """
        path.write_text(dedent(content).strip() + "\n", encoding="utf-8")

    def test_returns_and_prints_differences(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        Tests that two configuration files are correctly compared and the differences
        are both returned in a computer-readable format and printed to the console.
        One change for each category (changed, added, removed) is included in the test
        to ensure that all cases are handled correctly.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files.
        ``capsys`` : pytest.CaptureFixture[str]
            A pytest fixture that captures output to stdout and stderr during the test.
        """
        test_file_a = tmp_path / "config_a.yaml"
        test_file_b = tmp_path / "config_b.yaml"

        self._write_yaml(
            test_file_a,
            """
            pipeline_config:
                name: synthetic_pipeline
                output_dir: outputs
            stage_configs:
                stage_a:
                    years_to_run: 2026
                    target_variable: classification
            global_config:
                dry_run: True
            """,
        )

        self._write_yaml(
            test_file_b,
            """
            pipeline_config:
                name: synthetic_pipeline
                backend: python
            stage_configs:
                stage_a:
                    years_to_run: 2026
                    target_variable: identification
            global_config:
                dry_run: True
            """,
        )

        assert print_config_diffs(test_file_a, test_file_b) == {
            "changed": {
                "stage_configs.stage_a.target_variable": (
                    "classification",
                    "identification",
                )
            },
            "added": {"pipeline_config.backend": "python"},
            "removed": {"pipeline_config.output_dir": "outputs"},
        }

        test_file_b.write_text(
            dedent("""
                    pipeline_config:
                        name: synthetic_pipeline
                        backend: python
                    stage_configs:
                        stage_a:
                            years_to_run: 2026
                            target_variable: identification
                    global_config:
                        dry_run: True
                    """).strip()
            + "\n",
            encoding="utf-8",
        )

        assert print_config_diffs(test_file_a, test_file_b) == {
            "changed": {
                "stage_configs.stage_a.target_variable": (
                    "classification",
                    "identification",
                )
            },
            "added": {"pipeline_config.backend": "python"},
            "removed": {"pipeline_config.output_dir": "outputs"},
        }

        captured = capsys.readouterr()
        assert "CHANGED (1)" in captured.out
        assert "ADDED in second configuration (1)" in captured.out
        assert "REMOVED in second configuration (1)" in captured.out
        assert "stage_configs.stage_a.target_variable" in captured.out


class TestRunInfoWriteOut:
    def test_log_pipeline_attributes_writes_YAML(self, tmp_path: Path) -> None:
        """
        Tests that the ``_log_pipeline_attributes`` function correctly writes the pipeline attributes to a YAML file.
        """

        run_dir = tmp_path / "runs" / "synthetic_run"
        run_dir.mkdir(parents=True, exist_ok=True)

        pipeline_config = PipelineConfig(
            name="synthetic_pipeline",
            stages_to_run={"stage_a": True},
            backend="python",
            work_dir=tmp_path / "work",
            project_root=tmp_path,
            output_dir=tmp_path / "outputs",
            log_dir=tmp_path / "logs",
            data_dir=tmp_path / "data",
            allow_subprocess_fallback=True,
            python_executable=None,
            metadata={"reason": "unit test"},
        )

        context = ExecutionContext(
            pipeline_name="synthetic_pipeline",
            run_id="run_1234",
            config=pipeline_config,
            logger=Logger(),
            run_dir=run_dir,
            working_directory=tmp_path,
            stage_configs={},
            global_config=None,
        )

        stage_results = [
            StageResult(
                name="stage_a",
                status=StageStatus.SUCCEEDED,
                started_at=now(),
                finished_at=now(),
                error=None,
                source=None,
            )
        ]

        run_manifest = RunManifest(
            rap_name="synthetic_pipeline",
            run_id="run_1234",
        )

        pipeline_run = PipelineRun(
            manifest=run_manifest,
            status=PipelineStatus.SUCCEEDED,
            started_at=context.started_at,
            completed_at=now(),
            stage_results=stage_results,
            stage_outputs={},
        )

        _log_pipeline_attributes(
            pipeline_run=pipeline_run,
            run_dir=FileSystemSetUp.file_system_setup_factory(run_dir, path_type="dir"),
            context=context,
        )

        expected_file = run_dir / (
            "pipeline_attributes_for_"
            f"{context.pipeline_name}_{context.run_id[-8:]}.yaml"
        )

        expected_contents = pipeline_run._pipeline_run_to_dict()

        assert expected_file.exists()

        file_text = expected_file.read_text(encoding="utf-8")
        parsed_yaml = yaml.safe_load(file_text)
        assert parsed_yaml == expected_contents

        assert PipelineRun._pipeline_run_from_dict(parsed_yaml) == pipeline_run

    def test_log_pipeline_attributes_serializes_arbitrary_stage_outputs(
        self, tmp_path: Path
    ) -> None:
        """
        Tests that stage outputs containing non-YAML-native Python objects are
        serialized safely and can be reconstructed for supported types.
        """

        class CustomOutput:
            def __repr__(self) -> str:
                return "CustomOutput(example)"

        run_dir = tmp_path / "runs" / "synthetic_run"
        run_dir.mkdir(parents=True, exist_ok=True)

        context = ExecutionContext(
            pipeline_name="synthetic_pipeline",
            run_id="run_1234",
            config=PipelineConfig(name="synthetic_pipeline"),
            logger=Logger(),
            run_dir=run_dir,
            working_directory=tmp_path,
            stage_configs={},
            global_config=None,
        )

        run_manifest = RunManifest(
            rap_name="synthetic_pipeline",
            run_id="run_1234",
        )

        pipeline_run = PipelineRun(
            manifest=run_manifest,
            status=PipelineStatus.SUCCEEDED,
            started_at=context.started_at,
            completed_at=now(),
            stage_results=[],
            stage_outputs={
                "path_value": Path("data/interim/output.csv"),
                "datetime_value": datetime(2026, 8, 17, 12, 30, 45),
                "tuple_value": (1, "a"),
                "set_value": {1, 2},
                "bytes_value": b"abc",
                "bytearray_value": bytearray(b"xyz"),
                "custom_value": CustomOutput(),
            },
        )

        _log_pipeline_attributes(
            pipeline_run=pipeline_run,
            run_dir=FileSystemSetUp.file_system_setup_factory(run_dir, path_type="dir"),
            context=context,
        )

        expected_file = run_dir / (
            "pipeline_attributes_for_"
            f"{context.pipeline_name}_{context.run_id[-8:]}.yaml"
        )
        parsed_yaml = yaml.safe_load(expected_file.read_text(encoding="utf-8"))

        assert isinstance(parsed_yaml["stage_outputs"]["path_value"], dict)
        loaded_pipeline_run = PipelineRun._pipeline_run_from_dict(parsed_yaml)

        assert loaded_pipeline_run.stage_outputs["path_value"] == Path(
            "data/interim/output.csv"
        )
        assert loaded_pipeline_run.stage_outputs["datetime_value"] == datetime(
            2026, 8, 17, 12, 30, 45
        )
        assert loaded_pipeline_run.stage_outputs["tuple_value"] == (1, "a")
        assert loaded_pipeline_run.stage_outputs["set_value"] == {1, 2}
        assert loaded_pipeline_run.stage_outputs["bytes_value"] == b"abc"
        assert loaded_pipeline_run.stage_outputs["bytearray_value"] == bytearray(b"xyz")
        assert (
            loaded_pipeline_run.stage_outputs["custom_value"] == "CustomOutput(example)"
        )


class TestPipelineRunnerDunders:
    def test_pipeline_runner_default_init(self) -> None:
        """
        Tests that the PipelineRunner class can be initialized without errors.
        """
        from rap_toolkit.runner import PipelineRunner

        runner = PipelineRunner()
        assert runner is not None
        assert runner.logger is not None
        assert isinstance(runner.logger, Logger)

    def test_pipeline_runner_provided_init(self, tmp_path: Path) -> None:
        """
        Tests that the PipelineRunner class can be initialized with a provided Logger.
        """
        from rap_toolkit.runner import PipelineRunner

        tmp_logger_loc = tmp_path / "logs"
        tmp_fs = FileSystemSetUp.from_path(tmp_logger_loc, path_type="dir")
        custom_logger = Logger(log_dir=tmp_fs)
        runner = PipelineRunner(logger=custom_logger)
        assert runner is not None
        assert runner.logger is custom_logger
        assert runner.logger.log_dir == tmp_fs

    def test_pipeline_runner_str_method(self, tmp_path: Path) -> None:
        """
        Tests that the __str__ method of the PipelineRunner class returns a string
        representation containing the logger's log level.
        """
        from rap_toolkit.runner import PipelineRunner

        tmp_logger_loc = tmp_path / "logs"
        tmp_fs = FileSystemSetUp.from_path(tmp_logger_loc, path_type="dir")
        custom_logger = Logger(log_dir=tmp_fs)
        runner = PipelineRunner(logger=custom_logger)
        runner_str = str(runner)
        assert isinstance(runner_str, str)
        assert "PipelineRunner" in runner_str
        assert f"Logger: {runner.logger}" in runner_str

    def test_pipeline_runner_repr_method(self) -> None:
        """
        Tests that the __repr__ method of the PipelineRunner class returns a string
        representation containing the logger's log level.
        """
        from rap_toolkit.runner import PipelineRunner

        custom_logger = Logger(log_level="DEBUG")
        runner = PipelineRunner(logger=custom_logger)
        runner_repr = repr(runner)
        assert isinstance(runner_repr, str)
        assert f"PipelineRunner(logger={runner.logger})" in runner_repr


class TestRunnerBuildParser:
    def test_build_parser_returns_argument_parser(self) -> None:
        """
        Tests that build_parser() returns an argparse.ArgumentParser with the expected
        command line arguments.
        """
        from rap_toolkit.runner import build_parser

        parser = build_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog.endswith("pytest") or isinstance(parser.prog, str)

        option_strings = {
            option for action in parser._actions for option in action.option_strings
        }
        positional_destinations = [
            action.dest for action in parser._actions if not action.option_strings
        ]

        assert "--name" in option_strings
        assert "stages" in positional_destinations

    def test_build_parser_parses_typed_arguments(self) -> None:
        """
        Tests that build_parser() accepts a typed argv list and produces the expected
        namespace values.
        """
        from rap_toolkit.runner import build_parser

        parser = build_parser()
        argv: list[str] = ["stage_a.py", "stage_b.py", "--name", "demo pipeline"]
        namespace = parser.parse_args(argv)

        assert namespace.stages == ["stage_a.py", "stage_b.py"]
        assert isinstance(namespace.stages, list)
        assert all(isinstance(stage_name, str) for stage_name in namespace.stages)
        assert namespace.name == "demo pipeline"
        assert isinstance(namespace.name, str)


class TestRunnerMain:
    def test_main_builds_pipeline_and_runs_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tests that main() parses arguments, builds a pipeline from the parsed stage list,
        and runs that pipeline.
        """
        import rap_toolkit.runner as runner_module

        fake_pipeline = Mock()
        fake_pipeline.run = Mock(return_value=None)
        from_files_mock = Mock(return_value=fake_pipeline)

        parser = argparse.ArgumentParser()
        parser.add_argument("stages", nargs="+")
        parser.add_argument("--name", default=None)

        monkeypatch.setattr(runner_module, "build_parser", lambda: parser)
        monkeypatch.setattr("rap_toolkit.pipeline.Pipeline.from_files", from_files_mock)

        exit_code = runner_module.main(
            ["stage_a.py", "stage_b.py", "--name", "demo pipeline"]
        )

        assert exit_code == 0
        assert from_files_mock.call_count == 1
        assert from_files_mock.call_args.args[0] == ["stage_a.py", "stage_b.py"]
        assert from_files_mock.call_args.kwargs == {"name": "demo pipeline"}
        assert fake_pipeline.run.call_count == 1

    def test_main_passes_none_name_when_name_is_not_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tests that main() forwards a None pipeline name when --name is not supplied.
        """
        import rap_toolkit.runner as runner_module

        fake_pipeline = Mock()
        fake_pipeline.run = Mock(return_value=None)
        from_files_mock = Mock(return_value=fake_pipeline)

        parser = argparse.ArgumentParser()
        parser.add_argument("stages", nargs="+")
        parser.add_argument("--name", default=None)

        monkeypatch.setattr(runner_module, "build_parser", lambda: parser)
        monkeypatch.setattr("rap_toolkit.pipeline.Pipeline.from_files", from_files_mock)

        exit_code = runner_module.main(["stage_a.py"])

        assert exit_code == 0
        assert from_files_mock.call_args.args[0] == ["stage_a.py"]
        assert from_files_mock.call_args.kwargs == {"name": None}
        assert fake_pipeline.run.call_count == 1


@pytest.fixture
def runner_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from rap_toolkit.pipeline import Pipeline

    stage_source = tmp_path / "stage_a.py"
    stage_source.write_text(
        "def run(context):\n    return {'ok': True}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(Pipeline, "_load_latest_run", lambda self: None)
    monkeypatch.setattr(Pipeline, "_load_all_runs", lambda self: None)

    pipeline = Pipeline(
        name="runner_pipeline",
        config=PipelineConfig(
            name="runner_pipeline",
            stages_to_run={"stage_a": True},
            work_dir=tmp_path / "work",
            project_root=tmp_path,
            output_dir=tmp_path / "outputs",
            log_dir=tmp_path / "logs",
            data_dir=tmp_path / "data",
        ),
        stages=[Stage("stage_a", source=stage_source)],
        executor=Mock(name="executor"),
    )
    pipeline.stage_configs["stage_a"] = StageConfig(
        name="stage_a", _variables={"threshold": 3}
    )
    pipeline.global_config = GlobalConfig(_variables={"dry_run": True}, exclusion={})
    return pipeline


def _runtime_id() -> RuntimeID:
    timestamp = datetime(2026, 10, 7, 12, 34, 56)
    return RuntimeID(
        id="2026-10-07_123456_deadbeef",
        timestamp=timestamp,
        hash="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        short_hash="deadbeef",
    )


def _stage_result(name: str = "stage_a") -> StageResult:
    started_at = datetime(2026, 10, 7, 12, 34, 56)
    finished_at = datetime(2026, 10, 7, 12, 34, 57)
    return StageResult(
        name=name,
        status=StageStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        outputs={"ok": True},
    )


class TestRunnerRun:
    def test_run_success_path_updates_pipeline_and_returns_run(
        self, runner_pipeline, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tests the successful path through PipelineRunner.run().
        """
        from rap_toolkit.runner import PipelineRunner

        runner = PipelineRunner(
            logger=Logger(
                log_dir=FileSystemSetUp.from_path(
                    tmp_path / "runner_logs", path_type="dir"
                )
            )
        )
        runner.logger.event = Mock()

        runtime_id = _runtime_id()
        pipeline_manifest = RunManifest(
            rap_name=runner_pipeline.name, run_id=runtime_id.id
        )
        stage_result = _stage_result()
        log_config_mock = Mock()
        log_attributes_mock = Mock()
        now_values = iter(
            [
                datetime(2026, 10, 7, 12, 34, 56),
                datetime(2026, 10, 7, 12, 34, 58),
            ]
        )

        monkeypatch.setattr("rap_toolkit.runner._log_config", log_config_mock)
        monkeypatch.setattr(
            "rap_toolkit.runner._log_pipeline_attributes", log_attributes_mock
        )
        monkeypatch.setattr("rap_toolkit.runner.now", lambda: next(now_values))
        runner_pipeline.validate = Mock()
        runner_pipeline._create_runtime_id = Mock(return_value=runtime_id)
        runner_pipeline.ordered_stages = Mock(return_value=[runner_pipeline.stages[0]])
        runner_pipeline._construct_manifest = Mock(return_value=pipeline_manifest)

        observed_context = {}

        def run_stage(context, executor):
            observed_context["context"] = context
            assert context.active_stage_name == "stage_a"
            assert context.stage_config is not None
            assert context.stage_config.require("threshold") == 3
            assert context.global_config is runner_pipeline.global_config
            assert executor is runner_pipeline.executor
            return stage_result

        runner_pipeline.stages[0].run = Mock(side_effect=run_stage)

        run = runner.run(runner_pipeline)

        context = observed_context["context"]
        run_dir_path = context.run_dir.create_path()

        assert run.status == PipelineStatus.SUCCEEDED
        assert run is runner_pipeline.last_run
        assert runner_pipeline.manifest is pipeline_manifest
        assert runner_pipeline.id == runtime_id
        assert runner_pipeline.validate.called
        assert runner_pipeline._create_runtime_id.called
        assert runner_pipeline.ordered_stages.called
        assert runner_pipeline._construct_manifest.call_args == (
            (),
            {"runtime_id": runtime_id},
        )
        assert runner_pipeline.stages[0].run.called
        assert context.pipeline_name == runner_pipeline.name
        assert context.run_id == runtime_id.id
        assert context.config is runner_pipeline.config
        assert context.logger is runner.logger
        assert context.stage_results[stage_result.name] is stage_result
        assert context.variables[stage_result.name] == stage_result.outputs
        assert run_dir_path is not None
        assert run_dir_path.exists()
        assert pipeline_manifest.stages_run == [stage_result.name]
        assert pipeline_manifest.outputs == {stage_result.name: stage_result.outputs}
        assert run.stage_results == [stage_result]
        assert run.stage_outputs == {stage_result.name: stage_result.outputs}
        assert [call.args[0] for call in runner.logger.event.call_args_list] == [
            "Pipeline started",
            "Executing stage",
            "Pipeline completed",
        ]
        assert log_config_mock.call_count == 1
        assert log_attributes_mock.call_count == 1

    def test_run_records_failed_stage_and_reraises_stage_execution_error(
        self, runner_pipeline, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tests the StageExecutionError branch in PipelineRunner.run().
        """
        from rap_toolkit.runner import PipelineRunner

        runner = PipelineRunner(
            logger=Logger(
                log_dir=FileSystemSetUp.from_path(
                    tmp_path / "runner_logs", path_type="dir"
                )
            )
        )
        runner.logger.event = Mock()

        runtime_id = _runtime_id()
        pipeline_manifest = RunManifest(
            rap_name=runner_pipeline.name, run_id=runtime_id.id
        )
        failing_result = StageResult(
            name="stage_a",
            status=StageStatus.FAILED,
            started_at=datetime(2026, 10, 7, 12, 34, 56),
            finished_at=datetime(2026, 10, 7, 12, 34, 57),
            outputs={"partial": True},
            error="boom",
        )
        log_config_mock = Mock()
        log_attributes_mock = Mock()
        now_values = iter(
            [
                datetime(2026, 10, 7, 12, 34, 56),
                datetime(2026, 10, 7, 12, 34, 58),
            ]
        )

        monkeypatch.setattr("rap_toolkit.runner._log_config", log_config_mock)
        monkeypatch.setattr(
            "rap_toolkit.runner._log_pipeline_attributes", log_attributes_mock
        )
        monkeypatch.setattr("rap_toolkit.runner.now", lambda: next(now_values))
        runner_pipeline.validate = Mock()
        runner_pipeline._create_runtime_id = Mock(return_value=runtime_id)
        runner_pipeline.ordered_stages = Mock(return_value=[runner_pipeline.stages[0]])
        runner_pipeline._construct_manifest = Mock(return_value=pipeline_manifest)

        def fail_stage(context, executor):
            assert context.active_stage_name == "stage_a"
            raise StageExecutionError("stage failed", result=failing_result)

        runner_pipeline.stages[0].run = Mock(side_effect=fail_stage)

        with pytest.raises(StageExecutionError):
            runner.run(runner_pipeline)

        assert runner_pipeline.validate.called
        assert runner_pipeline._create_runtime_id.called
        assert runner_pipeline.ordered_stages.called
        assert runner_pipeline._construct_manifest.call_args == (
            (),
            {"runtime_id": runtime_id},
        )
        assert runner_pipeline.last_run is not None
        assert runner_pipeline.last_run.status == PipelineStatus.FAILED
        assert runner_pipeline.manifest is pipeline_manifest
        assert runner_pipeline.last_run.manifest is pipeline_manifest
        assert runner_pipeline.last_run.stage_results == [failing_result]
        assert runner_pipeline.last_run.stage_outputs == {"stage_a": {"partial": True}}
        assert pipeline_manifest.stages_run == ["stage_a"]
        assert pipeline_manifest.outputs == {"stage_a": {"partial": True}}
        assert [call.args[0] for call in runner.logger.event.call_args_list] == [
            "Pipeline started",
            "Executing stage",
            "Pipeline failed",
        ]
        assert log_config_mock.call_count == 1
        assert log_attributes_mock.call_count == 1
