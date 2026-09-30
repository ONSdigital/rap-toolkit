from __future__ import annotations


class RapToolkitWarning(Warning):
    """Base warning for `rap-toolkit`."""


class StageConfigurationWarning(RapToolkitWarning):
    """
    Raised when the stage configuration is not optimal.
    Child class with ``RapToolkitWarning`` as the parent class.
    """


class PipelineConfigurationWarning(RapToolkitWarning):
    """
    Raised when the pipeline configuration is not optimal.
    Child class with ``RapToolkitWarning`` as the parent class.
    """


class ConfigurationInjectionWarning(RapToolkitWarning):
    """
    Raised when the configuration injection is not optimal.
    Child class with ``RapToolkitWarning`` as the parent class.
    """
