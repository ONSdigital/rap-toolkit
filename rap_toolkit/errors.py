from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import StageResult


class RapToolkitError(Exception):
    """Base exception for `rap-toolkit`."""


class PipelineValidationError(RapToolkitError):
    """
    Raised when the pipeline definition is invalid.
    Child class with ``RapToolkitError`` as the parent class.
    """


class StageConfigurationError(PipelineValidationError):
    """
    Raised when a stage definition is malformed.
    Child class with ``PipelineValidationError`` as the parent class.
    """


class DuplicateStageError(PipelineValidationError):
    """
    Raised when two stages share the same name.
    Child class with ``PipelineValidationError`` as the parent class.
    """


class MissingDependencyError(PipelineValidationError):
    """
    Raised when a stage depends on an unknown stage.
    Child class with ``PipelineValidationError`` as the parent class.
    """


class DependencyCycleError(PipelineValidationError):
    """
    Raised when the stage graph contains a cycle.
    Child class with ``PipelineValidationError`` as the parent class.
    """


class StageExecutionError(RapToolkitError):
    """
    Raised when a stage fails during execution.
    Child class with ``RapToolkitError`` as the parent class.
    """

    def __init__(
        self,
        message: str,
        stage_name: str | None = None,
        source: str | None = None,
        original_exception: Exception | None = None,
        result: StageResult | None = None,
    ):
        super().__init__(message)
        self.stage_name = stage_name
        self.source = source
        self.original_exception = original_exception
        self.result = result


class StageLoadError(StageExecutionError):
    """
    Raised when a file-backed stage cannot be loaded.
    Child class with ``StageExecutionError`` as the parent class.
    """


class StageDependencyError(RapToolkitError):
    """
    Raised when incorrect inputs are provided to the dependency
    attribute of a Stage.
    """


class PipelineInitialisationError(RapToolkitError):
    """
    Raised when there is an error in definition of the Pipeline
    instance
    """


class PipelineConfigurationError(RapToolkitError):
    """
    Raised when there has been an issue with the PipelineConfig
    instance.
    """


class HistoricalPipelineLoadError(RapToolkitError):
    """
    Raised when there is an issue loading a previous PipelineRun
    instance.
    """
