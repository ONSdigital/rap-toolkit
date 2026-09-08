from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pyspark.sql import SparkSession

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp

from .errors import HistoricalPipelineLoadError


@dataclass
class LogConfig:
    """
    Data class which holds information regarding how the logs are set up.

    Parameters
    ----------
    ``log_dir`` : str, default = "logs/"
        The directory where all logs are stored for the Pipeline.
    ``log_level`` : str, default = "INFO"
        Denotes how severe the log message is.
    ``logger_name`` : str, default = "onsrap"
        The name of the logging system.
    """

    log_dir: FileSystemSetUp
    log_level: str = "INFO"
    logger_name: str = "onsrap"


class Logger:
    """
    Creates a logging system.

    This system creates a logging directory and enables writing the log messages
    to both console and the logging files. It allows configurable logging levels
    to adjust for severity and avoids duplicating logging messages or handlers.
    If the logger is unable to write to a file, the logging continues using only
    the console handler.

    Parameters
    ----------
    ``log_dir`` : FileSystemSetUp
        The file system setup for the directory where you'd like your logs stored.
    ``log_level`` : str, default = "INFO"
        The severity of the log.
    """

    _configured_loggers: set[str] = set()

    # TODO: do these loggers work with remote file systems? Does this matter? Should
    # probably be stored in Hive
    def __init__(
        self,
        log_dir: FileSystemSetUp | None = None,
        log_level: str = "INFO",
        spark_session: SparkSession | None = None,
    ):
        if log_dir is None:
            log_dir = FileSystemSetUp(
                workspace_path="logs", spark_session=spark_session
            )
        self.config = LogConfig(log_dir=log_dir, log_level=log_level)
        self.log_dir = log_dir

        self.file_system = FileSystemFactory.create(self.log_dir)
        self.file_system.mkdir(parents=True, exist_ok=True)

        self.spark_session = spark_session

        logger_name = f"{self.config.logger_name}:{self.log_dir}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(
            getattr(logging, self.config.log_level.upper(), logging.INFO)
        )
        if logger_name not in self._configured_loggers:
            self._logger.propagate = False

            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(stream_handler)

            try:
                file_handler = logging.FileHandler(
                    self.file_system.join_path("onsrap.log"), encoding="utf-8"
                )
                file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                self._logger.addHandler(file_handler)
            except OSError:
                pass

            self._configured_loggers.add(logger_name)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """
        Converts Logger instances to be callable, enabling easier implementation
        of logging.

        Positional arguemnts are converted to strings and joined with spaces.
        Keyword arguments are serialised as JSON and appended as structured
        context.
        """
        message = " ".join(str(arg) for arg in args)
        if kwargs:
            context = json.dumps(kwargs, default=str, sort_keys=True)
            message = f"{message} | {context}" if message else context
        self._logger.info(message)

    def __str__(self) -> str:
        """
        String method that returns a human-readable representation of the ``Logger``
        class.

        Returns
        -------
        str
            A string representation of the ``Logger`` class with its attributes.
        """
        return (
            f"Log Directory: {self.file_system.resolve(type='dir')}\n"
            f"     Log Level: {self.config.log_level}"
        )

    def __repr__(self) -> str:
        """
        Representation method that returns a human readable representation of the
        ``Logger`` class. This method is structured to be more concise than
        the ``__str__`` method and is intended for debugging purposes.

        Returns
        -------
        str
            A string representation of the ``Logger`` class with its attributes.
        """
        return f"Logger(log_dir={self.file_system.resolve(type='dir')}, log_level={self.config.log_level})"

    def event(self, message: str, **kwargs: Any) -> None:
        """
        Logs a named event with optional structured context.

        Parameters
        ----------
        ``message`` : str
            The main description of the event to be logged.
        ``**kwargs`` : Any
            Additional information to be recorded in the log record.
        """
        if kwargs:
            self._logger.info(
                "%s | %s", message, json.dumps(kwargs, default=str, sort_keys=True)
            )
        else:
            self._logger.info(message)

    def warning(self, message: str, **kwargs: Any) -> None:
        """
        Logs a warning message with optional structured context.

        Parameters
        ----------
        ``message`` : str
            The main description of the warning to be logged.
        ``**kwargs`` : Any
            Additional information to be recorded in the log record.
        """
        if kwargs:
            self._logger.warning(
                "%s | %s", message, json.dumps(kwargs, default=str, sort_keys=True)
            )
        else:
            self._logger.warning(message)

    def extract_historical_run_ids(
        self, run_root: FileSystemSetUp, name: str
    ) -> list[dict[str, Any]]:
        """
        Extracts historical run IDs from the log files.

        Parameters
        ----------
        ``run_root`` : FileSystemSetUp
            The root directory where the historical runs are stored.
        ``name`` : str
            The name of the pipeline for which to extract historical run IDs.

        Returns
        -------
        list[dict[str, Any]]
            A list of dictionaries containing run_id, timestamp, and run_dir for each historical run.
        """

        # confirms that run_root is a FileSystemSetUp instance and if not, creates it
        run_root = FileSystemSetUp.file_system_setup_factory(
            run_root, path_type="dir", spark_session=self.spark_session
        )

        # ensure that logger is writing to a file and extract filepath
        if not self._logger.hasHandlers():
            raise HistoricalPipelineLoadError(
                "The logger does not write to a"
                "filepath. Please ensure that your logger writes to a file path so that"
                "we can extract the run_id for historical runs."
            )

        logfile_handler = next(
            (h for h in self._logger.handlers if isinstance(h, logging.FileHandler)),
            None,
        )
        if logfile_handler is None:
            raise HistoricalPipelineLoadError(
                "The logger does not have a FileHandler. "
                "Please ensure that your logger writes to a file path so that we can extract the run_id "
                "for historical runs."
            )

        logfile_path = self.file_system.join_path(logfile_handler.baseFilename)
        logfile_path = FileSystemSetUp.from_any(
            str(logfile_path), path_type="file", spark_session=self.spark_session
        )

        new_fs = FileSystemFactory.update_fs(
            logfile_path, self.file_system, spark_session=self.spark_session
        )

        if not new_fs.exists(type="data"):
            raise HistoricalPipelineLoadError(
                "The log file does not exist at this location."
            )

        matches: list[dict[str, Any]] = []

        # TODO: This method works if the logs are recorded in chronological order. Would there
        # ever be a case where a record would appear below another and not be chronological?
        # If so, we may need to sort based on the timestamp rather than the ordering.
        for raw_line in reversed(new_fs.read_text(encoding="utf-8").splitlines()):
            if "Pipeline started" not in raw_line or " | " not in raw_line:
                continue

            # left: timestamp + message, right: JSON context
            left, right = raw_line.split(" | ", 1)

            # catches where Pipeline started is not recorded in the correct place.
            if not left.endswith(" Pipeline started"):
                continue

            # checks that datetime is valid
            timestamp = left[: -len(" Pipeline started")].strip()
            try:
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S,%f")
            except ValueError:
                continue

            try:
                payload = json.loads(right)
            except json.JSONDecodeError:
                continue

            run_id = payload.get("run_id")
            if not run_id:
                continue

            # timestamp is the first two space-separated tokens: YYYY-MM-DD HH:MM:SS,mmm
            parts = left.split(" ", 2)
            if len(parts) < 2:
                continue
            timestamp = f"{parts[0]} {parts[1]}"

            run_dir = str(run_root.create_uri() + "/" + run_id)
            run_dir_setup = FileSystemSetUp.from_any(
                run_dir, path_type="dir", spark_session=self.spark_session
            )
            run_dir_fs = FileSystemFactory.update_fs(
                run_dir_setup, self.file_system, spark_session=self.spark_session
            )
            # only returns run_ids for runs where a run_directory is still present.

            log_name = payload.get("name")
            if run_dir_fs.exists(type="dir") and log_name == name:
                matches.append(
                    {
                        "run_id": run_id,
                        "timestamp": timestamp,
                        "run_dir": run_dir,
                    }
                )

        return matches
