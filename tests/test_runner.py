from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from onsrap.execution import ExecutionContext
from onsrap.file_system_setup import FileSystemSetUp
from onsrap.logger import Logger
from onsrap.models import (
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    RunManifest,
    StageResult,
    StageStatus,
    now,
)
from onsrap.runner import _log_config, _log_pipeline_attributes, print_config_diffs


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

        expected_file = run_dir / (
            "configuration_for_"
            f"{context.pipeline_name}_{context.started_at.date()}_"
            f"{context.run_id[-8:]}.yaml"
        )

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
            run_dir=FileSystemSetUp.confirm_typing(run_dir, path_type="dir"),
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
            run_dir=FileSystemSetUp.confirm_typing(run_dir, path_type="dir"),
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
