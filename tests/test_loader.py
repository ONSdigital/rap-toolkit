from pathlib import Path

import pytest

from rap_toolkit.errors import StageLoadError
from rap_toolkit.loader import load_historical_run
from rap_toolkit.pipeline import PipelineRun
from tests.test_pipeline import TestLoadLatestRunIntegration


class TestLoadHistoricalRun(TestLoadLatestRunIntegration):
    def test_raises_stageloaderror_no_file(self, tmp_path: Path) -> None:
        """
        Checks that load_historical_run raises a StageLoadError when the specified
        directory does not contain any files matching the expected pattern.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.

        Raises
        ------
        ``StageLoadError``
            Raised when the specified directory does not contain any files matching
            the expected pattern for historical run YAML files.
        """
        run_dir = tmp_path / "empty_run"
        run_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(StageLoadError, match="Historical run file does not exist"):
            load_historical_run(run_dir=run_dir)

    def test_returns_valid_pipeline_run_from_yaml(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Checks that load_historical_run successfully returns a PipelineRun instance.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.
        """

        run_dir = tmp_path / "valid_run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "pipeline_attributes_for_test.yaml").write_text(
            minimal_pipeline_yaml(run_id="test_id"), encoding="utf-8"
        )

        result = load_historical_run(run_dir=run_dir)
        assert isinstance(result, PipelineRun)
        assert result.manifest.run_id == "test_id"

    def test_correct_yaml_file_chosen(
        self, tmp_path: Path, minimal_pipeline_yaml
    ) -> None:
        """
        Checks that if there are multiple files within the same run directory,
        the method will pass successfully and return a PipelineRun. This does
        not assert which file is chosen, only that the method does not raise
        an error and returns a PipelineRun instance.

        Logically, this should be suitable as we would only ever expect one file
        to be present in each run directory.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``minimal_pipeline_yaml`` : callable
            A fixture that returns a minimal YAML configuration for a historical run.
        """
        run_dir = tmp_path / "multiple_runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "pipeline_attributes_for_test1.yaml").write_text(
            minimal_pipeline_yaml(run_id="test_id_1"), encoding="utf-8"
        )
        (run_dir / "pipeline_attributes_for_test2.yaml").write_text(
            minimal_pipeline_yaml(run_id="test_id_2"), encoding="utf-8"
        )

        result = load_historical_run(run_dir=run_dir)
        assert isinstance(result, PipelineRun)
