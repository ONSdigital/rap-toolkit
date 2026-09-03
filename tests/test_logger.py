import logging
from pathlib import Path

import pytest

from onsrap.errors import HistoricalPipelineLoadError
from onsrap.file_system_setup import FileSystemSetUp
from onsrap.logger import Logger
from tests.test_pipeline import TestLoadLatestRunIntegration


class TestExtractHistoricalRunIds(TestLoadLatestRunIntegration):
    def test_logger_no_handler_errors(self, tmp_path: Path) -> None:
        """
        Tests that if the logger has no handlers, an error is raised when
        attempting to extract historical ids as the logger is not writing
        to a file that can be checked.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.

        Raises
        ------
        ``HistoricalPipelineLoadError``
            Raised when the logger does not have any handlers, indicating that
            it is not writing to a file path and cannot extract historical run ids.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )
        logger._logger.handlers.clear()  # Remove all handlers to simulate no file logging
        logger._logger.propagate = False  # Prevent checking root logger handlers
        with pytest.raises(HistoricalPipelineLoadError, match="does not write to a"):
            logger.extract_historical_run_ids(
                run_root=FileSystemSetUp.confirm_typing(
                    tmp_path / "runs", path_type="dir"
                ),
                name="test_pipeline",
            )

    def test_logger_no_file_handler_errors(self, tmp_path: Path) -> None:
        """
        Tests that if the logger has no file handlers, an error is raised when
        attempting to extract historical ids as the logger is not writing
        to a file that can be checked.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.

        Raises
        ------
        ``HistoricalPipelineLoadError``
            Raised when the logger does not have any handlers, indicating that
            it is not writing to a file path and cannot extract historical run ids.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )
        logger._logger.handlers = [logging.StreamHandler()]
        with pytest.raises(
            HistoricalPipelineLoadError, match="does not have a FileHandler"
        ):
            logger.extract_historical_run_ids(
                run_root=FileSystemSetUp.confirm_typing(
                    tmp_path / "runs", path_type="dir"
                ),
                name="test_pipeline",
            )

    def test_logger_does_not_exist(self, tmp_path: Path) -> None:
        """
         Checks that the method raises an error if the log doesn't exist at the
         location specified.

         Parameters
         ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        file_handler.close()
        log_path.unlink(
            missing_ok=True
        )  # Remove the log file to simulate non-existence

        with pytest.raises(
            HistoricalPipelineLoadError, match="does not exist at this location"
        ):
            logger.extract_historical_run_ids(
                run_root=FileSystemSetUp.confirm_typing(
                    tmp_path / "runs", path_type="dir"
                ),
                name="test_pipeline",
            )

    def test_return_blank_list_no_matches_in_log(self, tmp_path) -> None:
        """
        Tests that a log file that does not have a record covering "Pipeline started"
        will return a blank list from extract_historical_run_ids.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(
            "2026-08-10 10:00:00,000 Some unrelated log entry\n"
            "2026-08-10 10:00:01,000 | Another unrelated log entry\n"
            "2026-08-10 10:00:02,000 Pipeline Started\n"
        )

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result == []

    def test_skips_poor_json_in_log(self, tmp_path: Path) -> None:
        """
        Tests that if a JSON record in the log file is not valid, it will e skipped
        and the next valid entry will be extracted. Assert that the returned list
        contains only the valid entry. Confirms that only the incorrect record is
        skipped.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(
            "2026-08-10 10:00:00,000 Pipeline started | not_valid_json\n"
            '2026-08-10 10:00:01,000 Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_878fcb33"}\n'
            '2026-08-10 10:00:02,000 Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_abc1234"}\n'
        )

        create_run_dir_1 = tmp_path / "runs" / "2026-06-23_101719_878fcb33"
        create_run_dir_1.mkdir(parents=True, exist_ok=True)

        create_run_dir_2 = tmp_path / "runs" / "2026-06-23_101719_abc1234"
        create_run_dir_2.mkdir(parents=True, exist_ok=True)

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result == [
            {
                "run_id": "2026-06-23_101719_abc1234",
                "timestamp": "2026-08-10 10:00:02,000",
                "run_dir": FileSystemSetUp.confirm_typing(
                    tmp_path / "runs" / "2026-06-23_101719_abc1234", path_type="dir"
                ).create_uri(),
            },
            {
                "run_id": "2026-06-23_101719_878fcb33",
                "timestamp": "2026-08-10 10:00:01,000",
                "run_dir": FileSystemSetUp.confirm_typing(
                    tmp_path / "runs" / "2026-06-23_101719_878fcb33", path_type="dir"
                ).create_uri(),
            },
        ]

    @pytest.mark.parametrize(
        "string, expected", [('{"name":"test_pipeline"}', []), ('{"run_id":""}', [])]
    )
    def test_run_id_absent_falsy(
        self, tmp_path: Path, string: str, expected: list
    ) -> None:
        """
        Tests that if the JSON record in the log file does not have a run_id, it will be skipped
        and the returned list will be empty.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        ``string`` : str
            A dictionary representing a valid JSON record in the log file that excludes
            run_id.
        ``expected`` : list
            The expected output from extract_historical_run_ids when the log file
            contains a record without a run_id.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(f"2026-08-10 10:00:01,000 Pipeline started | {string}\n")

        # creates directory for runs to avoid removal given the directory doesn't exist
        (tmp_path / "runs").mkdir(parents=True, exist_ok=True)

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result == expected

    def test_records_only_if_directory_exists(self, tmp_path) -> None:
        """
        Checks that a record is only output if the run directory exists.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """

        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(
            '2026-08-10 10:00:01,000 Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_878fcb33"}\n'
            '2026-08-10 10:00:02,000 Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_abc1234"}\n'
        )

        create_run_dir_1 = tmp_path / "runs" / "2026-06-23_101719_878fcb33"
        create_run_dir_1.mkdir(parents=True, exist_ok=True)

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result == [
            {
                "run_id": "2026-06-23_101719_878fcb33",
                "timestamp": "2026-08-10 10:00:01,000",
                "run_dir": FileSystemSetUp.confirm_typing(
                    tmp_path / "runs" / "2026-06-23_101719_878fcb33", path_type="dir"
                ).create_uri(),
            }
        ]

    def test_reverse_chronological_order(self, tmp_path) -> None:
        """
        Checks that the run_ids are output in reverse chronological order
        based on their positioning in the log file.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(
            '2026-08-10 10:00:01,000 Pipeline started | {"name": "test_pipeline",'
            '"run_id": "2026-06-23_101719_878fcb33"}\n'
            '2026-08-10 10:00:02,000 Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_abc1234"}\n'
        )

        create_run_dir_1 = tmp_path / "runs" / "2026-06-23_101719_878fcb33"
        create_run_dir_1.mkdir(parents=True, exist_ok=True)

        create_run_dir_2 = tmp_path / "runs" / "2026-06-23_101719_abc1234"
        create_run_dir_2.mkdir(parents=True, exist_ok=True)

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result[0]["run_id"] == "2026-06-23_101719_abc1234"
        assert result[1]["run_id"] == "2026-06-23_101719_878fcb33"

    def test_skip_poor_timestamps(self, tmp_path) -> None:
        """
        Checks that entries with poor timestamps are skipped.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary directory provided by pytest for creating test files
            and directories.
        """
        logger = Logger(
            log_dir=FileSystemSetUp.confirm_typing(tmp_path / "logs", path_type="dir")
        )

        file_handler = next(
            h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)
        )

        log_path = Path(file_handler.baseFilename)

        log_path.write_text(
            'BADTIMESTAMP Pipeline started | {"name": "test_pipeline", '
            '"run_id": "2026-06-23_101719_878fcb33"}\n'
        )

        create_run_dir_1 = tmp_path / "runs" / "2026-06-23_101719_878fcb33"
        create_run_dir_1.mkdir(parents=True, exist_ok=True)

        result = logger.extract_historical_run_ids(
            run_root=FileSystemSetUp.confirm_typing(tmp_path / "runs", path_type="dir"),
            name="test_pipeline",
        )
        assert result == []
