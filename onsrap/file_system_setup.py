import glob
import importlib.util
import logging
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import IO, Optional, Protocol, Type


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
    ``file_name`` : str, Optional
        The name of the file to be accessed. This is optional as some methods require
        directory access only whereas this is used for a specific file location.
    """

    prefix: str
    root: str
    workspace_path: Optional[str] = None
    file_name: Optional[str] = None

    def create_uri(self) -> str:
        """
        Create a URI for the file system based on the prefix, root, and workspace path.

        Returns
        -------
        ``str``
            The constructed URI.
        """
        root = self.root.rstrip("/")
        if self.workspace_path:
            workspace_path = self.workspace_path.lstrip("/")
            if self.file_name:
                return f"{self.prefix}{root}/{workspace_path}/{self.file_name}"
            return f"{self.prefix}{root}/{workspace_path}"
        if self.file_name:
            return f"{self.prefix}{root}/{self.file_name}"
        return f"{self.prefix}{root}"

    @classmethod
    def from_str(cls, uri: str):
        """
        Derive a FileSystemSetUp object from a URI string.

        Parameters
        ----------
        ``uri`` : str
            The URI string to parse.

        Returns
        -------
        ``FileSystemSetUp``
            The derived FileSystemSetUp object.
        """
        prefix = uri.split("://")[0] + "://"
        sub_parts = uri.split("://")[1].split("/")
        file_name = sub_parts[-1] if "." in sub_parts[-1] else None
        subparts_no_file_name = sub_parts.pop() if file_name else sub_parts
        root = sub_parts[0]  # S3 bucket or home directory
        workspace_path = (
            "/".join(subparts_no_file_name) if subparts_no_file_name else None
        )
        return FileSystemSetUp(
            prefix=prefix, root=root, workspace_path=workspace_path, file_name=file_name
        )

    @classmethod
    def from_path(cls, path: Path):
        """
        Derive a FileSystemSetUp object from a Path object.

        Parameters
        ----------
        ``path`` : Path
            The Path object to parse.

        Returns
        -------
        ``FileSystemSetUp``
            The derived FileSystemSetUp object.
        """
        string_path = str(path)
        return cls.from_str(string_path)


class FileSystem(Protocol):
    """
    A Protocol that defines methods for the package to interact with different
    file systems. This ensures that there are set methods in place for every file
    system that we expect an interaction with to allow seamless integration.
    """

    @property
    def data_path(self) -> Path | str | None: ...

    @property
    def dir_path(self) -> Path | str: ...

    def __init__(
        self,
        setup: FileSystemSetUp,
    ): ...

    def exists(
        self,
        type: str,  # dir or data
    ) -> bool: ...

    def is_file(
        self,
    ) -> bool: ...

    def is_absolute(
        self,
        type: str,  # dir or data
    ) -> bool: ...

    def mkdir(
        self,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> None: ...

    def read_text(
        self,
        encoding: Optional[str] = "utf-8",
    ) -> str: ...

    def open(
        self,
        mode: str = "r",
        encoding: Optional[str] = "utf-8",
    ) -> IO: ...

    def glob(
        self,
        specific_pattern: str,
    ) -> list[str]: ...

    def expand_user(
        self,
    ) -> FileSystemSetUp | str | Path: ...

    def resolve(
        self,
        type: str,  # dir or data
    ) -> str | Path: ...

    def spec_from_file_location(
        self,
        module_name: str,
    ): ...

    def file_handler(
        self,
        file_name: str,
        encoding: str,
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
        ``setup`` : FileSystemSetUp
            The setup information containing the prefix, root, and workspace path.
        """
        root = Path(setup.root)
        self.dir_path: Path = (
            root / setup.workspace_path if setup.workspace_path else root
        )
        self.data_path: Path | None = (
            self.dir_path / setup.file_name if setup.file_name else None
        )

    def __str__(self) -> str:
        """
        Return a string representation of the LocalFileSystem.

        Returns
        -------
        ``str``
            A string representation of the LocalFileSystem, including the directory
            and data paths.
        """
        return (
            f"Local File System:\n"
            f"Directory Path: {self.dir_path}\nData Path: {self.data_path}"
        )

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the LocalFileSystem.

        Returns
        -------
        ``str``
            A detailed string representation of the LocalFileSystem, including the
            directory and data paths.
        """
        return (
            f"LocalFileSystem(dir_path={self.dir_path!r}, data_path={self.data_path!r})"
        )

    def exists(
        self,
        type: str,  # dir or data
    ) -> bool:
        """
        Check if the path exists in the local file system.

        This utilises the pathlib Path.exists() method.

        Returns
        -------
        ``bool``
            True if the path exists, False otherwise.

        Raises
        ------
        ValueError
            If the type specified is not 'dir' or 'data'.
        """
        if type == "dir":
            return self.dir_path.exists()
        elif type == "data":
            if self.data_path:
                return self.data_path.exists()
            else:
                raise ValueError(
                    "Data path is not set. Cannot check existence of data file."
                )
        else:
            raise ValueError("Invalid type specified. Use 'dir' or 'data'.")

    def is_file(
        self,
    ) -> bool:
        """
        Checks if the path is a file in the local file system.
        This utilises the pathlib Path.is_file() method.

        Returns
        -------
        ``bool``
            True if the path is a file, False otherwise.
        """
        if self.data_path:
            return self.data_path.is_file()
        else:
            raise ValueError("Data path is not set. Cannot check if it is a file.")

    def is_absolute(
        self,
        type: str,  # dir or data
    ) -> bool:
        """
        Checks if the path is an absolute path in the local file system.
        This utilises the pathlib Path.is_absolute() method.

        Returns
        -------
        ``bool``
            True if the path is absolute, False otherwise.
        """
        if type == "dir":
            return self.dir_path.is_absolute()
        elif type == "data":
            if self.data_path:
                return self.data_path.is_absolute()
            else:
                raise ValueError(
                    "Data path is not set. Cannot check if it is absolute."
                )
        else:
            raise ValueError("Invalid type specified. Use 'dir' or 'data'.")

    def mkdir(
        self,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> None:
        """
        Creates a directory at the specified path in the local file system.

        Parameters
        ----------
        ``parents`` : bool, default = True
            If True, create parent directories as needed. If False, raise an error if
            the parent directory does not exist.
        ``exist_ok`` : bool, default = True
            If True, do not raise an error if the target directory already exists.
        """
        self.dir_path.mkdir(parents=parents, exist_ok=exist_ok)

    def read_text(
        self,
        encoding: Optional[str] = "utf-8",
    ) -> str:
        """
        Read the content of the data file as text.

        Parameters
        ----------
        ``encoding`` : Optional[str], default = "utf-8"
            The encoding to use when reading the file.

        Returns
        -------
        ``str``
            The content of the data file as a string.
        """
        if not self.data_path:
            raise ValueError("Data path is not set. Cannot read text from a file.")
        return self.data_path.read_text(encoding=encoding)

    def open(
        self,
        mode: str = "r",
        encoding: Optional[str] = "utf-8",
    ) -> IO:
        """
        Open the data file in the local file system.

        Parameters
        ----------
        ``mode`` : str, default = "r"
            The method in which to open the file (e.g., "r" for reading, "w" for writing).
        ``encoding`` : Optional[str], default = "utf-8"
            The encoding to use when opening the file.

        Returns
        -------
        ``IO``
            A file object corresponding to the opened file.
        """
        if not self.data_path:
            raise ValueError("Data path is not set. Cannot open a file.")
        file = self.data_path
        return open(file, mode=mode, encoding=encoding)

    def glob(
        self,
        specific_pattern: str,
    ) -> list:
        """
        Perform a glob operation on the directory path in the local file system
        to identify files matching the string input.

        Parameters
        ----------
        ``specific_pattern`` : str
            The glob pattern to match files against (e.g., "*.txt" for all text files).

        Returns
        -------
        ``list``
            A list of paths matching the glob pattern.
        """
        output = glob.glob(str(self.dir_path / specific_pattern))
        return output

    def expand_user(
        self,
    ) -> Path:
        """
        Expands the user tilde (~) in the path.

        Returns
        -------
        ``Path``
            The path with the user tilde expanded.
        """
        return (
            self.data_path.expanduser()
            if self.data_path
            else self.dir_path.expanduser()
        )

    def resolve(
        self,
        type: str,  # dir or data
    ) -> Path:
        """
        Resolves the filepath to an absolute path.

        Parameters
        ----------
        ``type`` : str
            The type of path to resolve. Should be either 'dir' for the directory path
            or 'data' for the data file path.

        Returns
        -------
        ``Path``
            The resolved absolute path.

        Raises
        ------
        ``ValueError``
            If the type specified is not 'dir' or 'data'.
        """
        if type == "dir":
            return self.dir_path.resolve()
        elif type == "data":
            if self.data_path:
                return self.data_path.resolve()
            else:
                raise ValueError("Data path is not set. Cannot resolve data path.")
        else:
            raise ValueError("Invalid type. Expected 'dir' or 'data'.")

    def spec_from_file_location(
        self,
        module_name: str,
    ) -> ModuleSpec | None:
        """
        Get the module spec from the file location.

        Parameters
        ----------
        ``module_name`` : str
            The name of the module.

        Returns
        -------
        ``ModuleSpec`` or None
            The module spec corresponding to the data file, or None if it cannot be determined.
        """
        return importlib.util.spec_from_file_location(module_name, str(self.data_path))

    def file_handler(
        self,
        file_name: str,
        encoding: str,
    ):
        """
        Get a file handler for the specified file in the directory.

        Parameters
        ----------
        ``file_name`` : str
            The name of the file for which to create the handler.
        ``encoding`` : str
            The encoding to use for the file handler.

        Returns
        -------
        ``logging.FileHandler``
            A file handler for the specified file.
        """
        return logging.FileHandler(str(self.dir_path / file_name), encoding=encoding)


# TODO: add a FileSystem for S3 when LFS one is stable


class FileSystemFactory:
    _registry: dict[str, Type[FileSystem]] = {}

    @classmethod
    def register(cls, prefix: str, fs_class: Type[FileSystem]) -> None:
        """
        Register a file system class with a specific prefix.

        Parameters
        ----------
        ``prefix`` : str
            The prefix associated with the file system (e.g., 's3a://', 'file://').
        ``fs_class`` : Type[FileSystem]
            The class implementing the FileSystem protocol.
        """
        cls._registry[prefix] = fs_class

    @classmethod
    def create(cls, setup: FileSystemSetUp) -> FileSystem:
        """
        Create an instance of the appropriate file system class based on the prefix.

        Parameters
        ----------
        ``setup`` : FileSystemSetUp
            The setup information containing the prefix and other details.

        Returns
        -------
        ``FileSystem``
            An instance of the appropriate file system class.

        Raises
        ------
        ``ValueError``
            If no registered file system class is found for the given prefix.
        """
        fs_class = cls._registry.get(setup.prefix)
        if not fs_class:
            raise ValueError(
                f"No registered file system class for prefix: {setup.prefix}"
            )
        return fs_class(setup)

    @classmethod
    def update(cls, path: str, fs: FileSystem) -> tuple[FileSystem, FileSystemSetUp]:
        """
        Update the file system instance with a new setup.

        Parameters
        ----------
        ``setup`` : FileSystemSetUp
            The new setup information.
        ``fs`` : FileSystem
            The existing file system instance to update.

        Returns
        -------
        ``FileSystem``
            An updated instance of the appropriate file system class.
        """
        setup = FileSystemSetUp.from_str(path)
        fs = cls.create(setup)
        return fs, setup


# Registering the file system classes with their respective prefixes
FileSystemFactory.register("file://", LocalFileSystem)
