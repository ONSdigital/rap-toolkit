from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Type


@dataclass
class FileSystemSetUp:
    """
    A class that holds information relevant to determining the file system being used.

    Parameters
    ----------
    ``prefix`` : str
        The file path prefix. This should be s3a:// for s3 file systems and file://
        for absolute locations in local file systems. This is removed in the factory
        method to allow for compatability with file systems that do not require a
        prefix.
    ``root`` : str
        The root of the storage location.
        For local:    the absolute base directory (e.g. /home/cdsw/project or
                                                        /C:/Users/project)
        For S3:       the bucket name (e.g. my-bucket)
    ``workspace_path`` : str, Optional
        The file subpath to access a lower level of file directory. This should be
        used for S3 to access your workspace area within the bucket.

    """

    prefix: str
    root: str
    workspace_path: Optional[str] = None

    def create_uri(self) -> str:
        """
        Create a URI for the file system based on the prefix, root, and workspace path.

        Returns
        -------
        str
            The constructed URI.
        """
        root = self.root.rstrip("/")
        if self.workspace_path:
            workspace_path = self.workspace_path.lstrip("/")
            return f"{self.prefix}{root}/{workspace_path}"
        return f"{self.prefix}{root}"


class FileSystem(Protocol):
    """
    A Protocol that defines methods for the package to interact with different
    file systems. This ensures that there are set methods in place for every file
    system that we expect an interaction with to allow seamless integration.
    """

    def __init__(
        self,
        setup: FileSystemSetUp,
    ): ...

    def exists(
        self,
    ): ...

    def is_file(
        self,
    ): ...

    def is_absolute(
        self,
    ): ...

    def mkdir(
        self,
    ): ...

    def read_text(
        self,
    ): ...

    def open(
        self,
    ): ...

    def glob(
        self,
    ): ...

    def expand_user(
        self,
    ): ...

    def resolve(
        self,
    ): ...

    def spec_from_file_location(
        self,
    ): ...

    def file_handler(
        self,
    ): ...


# TODO: do we need a separate protocol to cover local file systems? specific
# interactions like creating directories, reading/writing files, etc. might
# be different than S3 or other file systems so methods may not be worth
# including in core protocol.


class LocalFileSystem:
    """
    A class that holds methods for interacting with the local file system.
    This class will utilise Path methodology to create, read, and write to
    the local file system.

    This class is part of the FileSystem Protocol.
    """

    def __init__(self, setup: FileSystemSetUp):
        """
        Initialize the LocalFileSystem with the provided setup.

        Parameters
        ----------
        setup : FileSystemSetUp
            The setup information containing the prefix, root, and workspace path.
        """
        root = Path(setup.root)
        self.path = root / setup.workspace_path if setup.workspace_path else root

    def exists(
        self,
    ): ...

    def is_file(
        self,
    ): ...

    def is_absolute(
        self,
    ): ...

    def mkdir(
        self,
    ): ...

    def read_text(
        self,
    ): ...

    def open(
        self,
    ): ...

    def glob(
        self,
    ): ...

    def expand_user(
        self,
    ): ...

    def resolve(
        self,
    ): ...

    def spec_from_file_location(
        self,
    ): ...

    def file_handler(
        self,
    ): ...


# TODO: edit this docstring with whether Boto3 or Spark is used
class S3FileSystem:
    """
    A class that holds methods for interacting with the S3 file system.
    This class will utilise Boto3/Spark methodology to create, read, and write to
    the S3 file system.

    This class is part of the FileSystem Protocol.
    """

    def __init__(self, setup: FileSystemSetUp):
        """
        Initialize the S3FileSystem with the provided setup.

        Parameters
        ----------
        setup : FileSystemSetUp
            The setup information containing the prefix, root, and workspace path.
        """
        self.path = setup.create_uri()

    def exists(
        self,
    ): ...

    def is_file(
        self,
    ): ...

    def is_absolute(
        self,
    ): ...

    def mkdir(
        self,
    ): ...

    def read_text(
        self,
    ): ...

    def open(
        self,
    ): ...

    def glob(
        self,
    ): ...

    def expand_user(
        self,
    ): ...

    def resolve(
        self,
    ): ...

    def spec_from_file_location(
        self,
    ): ...

    def file_handler(
        self,
    ): ...


class FileSystemFactory:
    _registry: dict[str, Type[FileSystem]] = {}

    @classmethod
    def register(cls, prefix: str, fs_class: Type[FileSystem]) -> None:
        """
        Register a file system class with a specific prefix.

        Parameters
        ----------
        prefix : str
            The prefix associated with the file system (e.g., 's3a://', 'file://').
        fs_class : Type[FileSystem]
            The class implementing the FileSystem protocol.
        """
        cls._registry[prefix] = fs_class

    @classmethod
    def create(cls, setup: FileSystemSetUp) -> FileSystem:
        """
        Create an instance of the appropriate file system class based on the prefix.

        Parameters
        ----------
        setup : FileSystemSetUp
            The setup information containing the prefix and other details.

        Returns
        -------
        FileSystem
            An instance of the appropriate file system class.

        Raises
        ------
        ValueError
            If no registered file system class is found for the given prefix.
        """
        fs_class = cls._registry.get(setup.prefix)
        if not fs_class:
            raise ValueError(
                f"No registered file system class for prefix: {setup.prefix}"
            )
        return fs_class(setup)


# Registering the file system classes with their respective prefixes
FileSystemFactory.register("file://", LocalFileSystem)
FileSystemFactory.register("s3a://", S3FileSystem)
