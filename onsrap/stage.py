from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp

from .errors import StageConfigurationError, StageDependencyError

if TYPE_CHECKING:
    from .execution import ExecutionContext, StageExecutor
    from .models import StageResult


def _normalize_dependencies(
    dependencies: Iterable[str] | str | None,
) -> tuple[str, ...]:
    """
    Standardise the names of any stages dependant on other stages/processes.

    Removes trailing or leading white space from the name of any stage/process dependant
    on another and turns it into a tuple of strings.

    Parameters
    ----------
    dependencies : Iterable[str] | str | None
        Dependency names to standardise. ``None`` returns an empty tuple. A
        string is treated as a single entry in the tuple. Any iterable is converted
        into a sequence of names.
    Returns
    -------
    normalized : tuple
        A tuple of cleaned dependency names.
    """
    if dependencies is None:
        return ()
    if isinstance(dependencies, list) and dependencies == []:
        return ()
    if isinstance(dependencies, str):
        candidate_items: Iterable[str]
        candidate_items = [dependencies]

    else:
        candidate_items = dependencies

    normalized: list[str] = []

    for dependency in candidate_items:
        dependency_name = str(dependency).strip()
        if dependency_name and dependency_name not in normalized:
            normalized.append(dependency_name)

    return tuple(normalized)


@dataclass
class Stage:
    """
    Represents a single unit of work within a pipeline.

    Can be defined by a data source process or a Python script/callable item.
    Stages may be dependant on other stages and can hold metadata for themselves.

    Parameters
    ----------
    ``name`` : str
        The name of the Stage being run.
    ``source`` : FileSystemSetUp, Path, Callable, str, or None
        Item being implemented in this Stage. E.g. a file path to a Python script
        stored as a FileSystemSetUp object or a function being executed directly.
        The full file path is gathered if a path is used.
    ``dependencies`` : tuple of strings
        Names of stages that must be completed before this stage is attempted. These
        are cleaned post initialisation to remove leading/trailing whitespace.
    ``metadata`` : dictionary with string:Any key/value pairs
        Location to store any summary information about the stage being run.
    ``entrypoint``: str, optional
        Name of the starting script to the pipeline.
    ``backend`` : str, default = "python"
        The name of the system that the code runs on.

    Raises
    ------
    ``StageConfigurationError``
        If the stage ``name`` is empty or if the source is not a supported type.
    """

    name: str
    source: FileSystemSetUp | Path | Callable[..., Any] | str | None = None
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    entrypoint: Optional[str] = None
    backend: str = "python"

    def __post_init__(self) -> None:
        self.name = str(self.name).strip()
        if not self.name:
            raise StageConfigurationError("Stage name cannot be empty.")

        if self.source is not None and not callable(self.source):
            self.source = FileSystemSetUp.confirm_typing(self.source, path_type="file")
            if not isinstance(self.source, (FileSystemSetUp, Path, str)):
                raise StageConfigurationError(
                    "Stage source must be a FileSystemSetUp, Path, string, callable, or None."
                )

        self.dependencies = _normalize_dependencies(self.dependencies)
        self.metadata = dict(self.metadata or {})
        self.backend = str(self.backend or "python").strip() or "python"

    def __str__(self) -> str:
        """
        String method that returns a human-readable representation of the ``Stage`` class.

        Returns
        -------
        str
            A string representation of the ``Stage`` class with its attributes.
        """
        return (
            f"    Name: {self.name}\n    Source: {self.source_label} \n"
            f"    Dependencies: {self.dependencies}\n    Metadata: {self.metadata} \n"
            f"    Entrypoint: {self.entrypoint} \n    Backend: {self.backend}"
        )

    def __repr__(self) -> str:
        """
        Representation method that returns a human readable representation of the ``Stage`` class.
        This method is structured to be more concise than the ``__str__`` method and is intended for
        debugging purposes.

        Returns
        -------
        str
            A string representation of the ``Stage`` class with its attributes.
        """
        return (
            f"Stage(name={self.name}, source={self.source_label}, "
            f"dependencies={self.dependencies}, metadata={self.metadata}, "
            f"entrypoint={self.entrypoint}, backend={self.backend})"
        )

    @classmethod
    def from_file(
        cls,
        file_path: FileSystemSetUp,
        *,
        name: str | None = None,
        dependencies: Iterable[str] | str | None = None,
        metadata: Mapping[str, Any] | None = None,
        entrypoint: str | None = None,
        backend: str = "python",
    ) -> Stage:
        """
        Class method that checks and cleans the file path for the ``Stage``.

        Expands file path to its full name and checks whether it exists. The method
        also cleans other parameters in the Stage class in the return line.

        Parameters
        ----------
        if not file_path.exists(type="data"):
            raise StageConfigurationError(f"Stage source file does not exist: {file_path}")

        return cls(
            name=name or file_path.file_name.stem,
            source=file_path,
            dependencies=_normalize_dependencies(dependencies),
            metadata=dict(metadata or {}),
            entrypoint=entrypoint,
            backend=backend,
        )

        Raises
        ------
        StageConfigurationError
            If the file path does not exist

        Returns
        -------
        Stage
            Stage class instance with cleaned/checked file path, dependencies, and metadata
        """
        file_system = FileSystemFactory.create(file_path)
        path = file_system.expand_user()
        if not file_system.exists(type="data"):
            raise StageConfigurationError(f"Stage source file does not exist: {path}")

        return cls(
            name=name or file_path.file_name
            if file_path.file_name is not None
            else "stage",
            source=path,
            dependencies=_normalize_dependencies(dependencies),
            metadata=dict(metadata or {}),
            entrypoint=entrypoint,
            backend=backend,
        )

    @classmethod
    def from_callable(
        cls,
        callable_object: Callable[..., Any],
        *,
        name: str | None = None,
        dependencies: Iterable[str] | str | None = None,
        metadata: Mapping[str, Any] | None = None,
        backend: str = "python",
    ) -> Stage:
        """
        Class method that retrieves the name of the Stage from a Callable item.

        Parameters
        ----------
        ``callable_object`` : Callable with any number of arguments of any type
            The name or file path for the script that the Stage will be running.
        ``name`` : str
            The name of the Stage
        ``dependencies`` : Iterable[str], str, or None
            The Stage/s that need to be complete before the Stage currently attempted.
        ``metadata`` : Mapping[str, Any], or None
            Any supporting information for the Stage being run.
        ``entrypoint`` : str or None
            The name of the first script for the Stage.
        ``backend``: str, default = "python"
            The system that the stage is run on.

        Returns
        -------
        ``Stage``
            ``Stage class`` instance with collected Stage ``name``, normalised ``dependencies``
            and ``metadata``, and defined the source as the callable_object.
        """
        stage_name = str(name or getattr(callable_object, "__name__", "stage"))
        return cls(
            name=stage_name,
            source=callable_object,
            dependencies=_normalize_dependencies(dependencies),
            metadata=dict(metadata or {}),
            backend=backend,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Stage:
        """
        Class method that converts a dictionary stage into a ``Stage`` class instance.

        Extracts the values from the key/value pairs in the stage and holds them as attributes.

        Parameters
        ----------
        ``data`` : any number of key/value pairs of strings
            The information to convert into a Stage class.

        Raises
        ------
        ``StageConfigurationError``
            If the source is not a suitable type (callable or Path).

        Returns
        -------
        ``Stage``
            ``Stage`` class instance with collected ``Stage`` attributes based on the type of ``source``
            provided.
        """
        payload = dict(data)

        source = payload.pop("source", payload.pop("path", None))
        callable_source = payload.pop("callable", None)
        dependencies = payload.pop("dependencies", ())
        metadata = payload.pop("metadata", {})
        entrypoint = payload.pop("entrypoint", None)
        backend = payload.pop("backend", "python")
        raw_name = payload.pop("name", None)
        name = str(raw_name).strip() if raw_name is not None else None

        if isinstance(metadata, Mapping):
            metadata = dict(metadata)
        else:
            metadata = {"metadata": metadata}

        if callable(source):
            return cls.from_callable(
                source,
                name=name,
                dependencies=dependencies,
                metadata=metadata,
                backend=backend,
            )

        if callable(callable_source):
            return cls.from_callable(
                callable_source,
                name=name,
                dependencies=dependencies,
                metadata=metadata,
                backend=backend,
            )

        if source is not None:
            return cls.from_file(
                source,
                name=name,
                dependencies=dependencies,
                metadata=metadata,
                entrypoint=entrypoint,
                backend=backend,
            )

        raise StageConfigurationError(
            "Stage dictionary must define a source, path, or callable."
        )

    def with_dependencies(self, *dependencies: str) -> Stage:
        """
        Method that normalises and adds ``dependencies`` to the ``Stage`` class attributes.

        Parameters
        ----------
        ``*dependencies`` : str
            Information on which scripts need to run before other scripts for this ``Stage``.

        Returns
        -------
        ``Stage``
            ``Stage`` class instance with normalised ``dependencies`` attribute.
        """
        unpacked_deps: list[str] = []
        for dependency in dependencies:
            if isinstance(dependency, list):
                unpacked_deps = unpacked_deps + dependency
            else:
                unpacked_deps.append(dependency)

        for dependency in unpacked_deps:
            if isinstance(dependency, list):
                raise StageDependencyError(
                    "Nested lists are not valid arguments for this method! "
                    "Please provided single list or individual string values"
                )

        return replace(
            self,
            dependencies=self.dependencies + _normalize_dependencies(unpacked_deps),
        )

    def validate(self) -> None:
        """
        Error checking on source attribute.

        Raises
        -------
        ``StageConfigurationError``
            If ``source`` attribute does not define a source or does not exist.
        """
        if not (isinstance(self.source, FileSystemSetUp) or callable(self.source)):
            raise StageConfigurationError(
                f"Stage '{self.name}' must have a Path or Callable source."
            )

        if self.source is None or self.source == "":
            raise StageConfigurationError(
                f"Stage '{self.name}' does not define a source. Source provided: {self.source}"
            )

        if isinstance(self.source, FileSystemSetUp):
            fs = FileSystemFactory.create(self.source)
            if not fs.is_file():
                raise StageConfigurationError(
                    f"Stage source does not exist: {self.source}"
                )

    @property
    def source_path(self) -> Optional[str]:
        """
        Sets a property for the ``Stage`` class if the ``source`` is a FileSystemSetUp.

        Returns
        -------
        ``str``
            Version of the ``source`` attribute as a string if it is a FileSystemSetUp. Otherwise, returns None.
        """
        if isinstance(self.source, FileSystemSetUp):
            return self.source.create_uri()
        return None

    @property
    def source_label(self) -> Optional[str]:
        """
        Sets a property for the ``Stage`` class with a human-readable name for the ``source``.

        Returns
        -------
        ``source_label`` attribute to the ``Stage`` class if ``source`` is a callable or Path.
        """
        if callable(self.source):
            return f"{getattr(self.source, '__module__', '<callable>')}.{getattr(self.source, '__name__', self.name)}"

        if isinstance(self.source, FileSystemSetUp):
            return self.source.create_uri()

        return None

    def run(self, context: ExecutionContext, executor: StageExecutor) -> StageResult:
        """
        Checks that the ``source`` is valid and then runs the ``source``

        Properties
        ----------
        context : set value "ExecutionContext"
            Uses ``ExecutionContext`` class information to provide required metadata on running ``source``.
            Any stage-specific configuration resolved by the ``Pipeline`` is available through
            ``context.stage_config`` while this stage is running.
        executor : set value "StageExecutor"
            Uses ``StageExecutor`` class to extract the ``.execute`` method to actually run the ``source``.

        Returns
        -------
        ``execute`` method of the ``StageExecutor`` class stored in the ``StageResult`` class.
        """
        self.validate()
        return executor.execute(self, context)
