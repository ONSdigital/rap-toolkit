import glob
import importlib.util
import logging
import re
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from pathlib import Path, PurePosixPath
from typing import IO, Any, Optional, Protocol, Type
from urllib.parse import unquote, urlparse, urlsplit

WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")


@dataclass
class FileSystemSetUp:
    """
    A class that holds information relevant to determining the file system being used.

    Defaults to current working directory in Local File Systems using Pathlib. This
    will not be functional with remote file systems and therefore care must be taken when
    defaulting FileSystemSetUp.

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

    prefix: str = "file:///"
    root: str = str(Path.cwd().resolve())
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
    def from_str(cls, uri: str, path_type: str = "file"):
        """
        Derive a FileSystemSetUp object from a URI string.

        Parameters
        ----------
        ``uri`` : str
            The URI string to parse.
        ``path_type`` : str, optional
            The type of the file system, by default "file".

        Returns
        -------
        ``FileSystemSetUp``
            The derived FileSystemSetUp object.
        """
        normalised_uri = cls._normalisation(uri)
        prefix, root, workspace_path, file_name = cls._uri_to_parts(
            normalised_uri, path_type
        )
        return FileSystemSetUp(
            prefix=prefix, root=root, workspace_path=workspace_path, file_name=file_name
        )

    @classmethod
    def from_path(cls, path: Path, path_type: str = "file"):
        """
        Derive a FileSystemSetUp object from a Path object.

        Parameters
        ----------
        ``path`` : Path
            The Path object to parse.
        ``path_type`` : str, optional
            The type of output the path leads to, by default "file".

        Returns
        -------
        ``FileSystemSetUp``
            The derived FileSystemSetUp object.
        """
        normalised_path = cls._normalisation(path)
        prefix, root, workspace_path, file_name = cls._uri_to_parts(
            normalised_path, path_type
        )
        return FileSystemSetUp(
            prefix=prefix, root=root, workspace_path=workspace_path, file_name=file_name
        )

    @classmethod
    def from_any(cls, path: Any, path_type: str = "file"):
        """
        Derive a FileSystemSetUp object from either a URI string or a Path object.

        Parameters
        ----------
        ``path`` : Any
            The input path to parse, which can be either a URI string or a Path object.
        ``path_type`` : str, optional
            The type of output the path leads to, by default "file".

        Returns
        -------
        ``FileSystemSetUp``
            The derived FileSystemSetUp object.
        """
        if isinstance(path, FileSystemSetUp):
            return path
        elif isinstance(path, str):
            return cls.from_str(path, path_type)
        elif isinstance(path, Path):
            return cls.from_path(path, path_type)
        elif path is None:
            raise ValueError("Input path cannot be None.")
        else:
            raise TypeError(
                f"Your input is not a str/Path and cannot be converted to one. Please check your input type: {type(path)}."
            )

    @staticmethod
    def _classification(input: str) -> str:
        """
        Classify whether the input is already in a URI format.
        This works based on the assumption that any filepaths that do not have a
        specified URI prefix are local file systems.

        Parameters
        ----------
        ``input`` : Path | str
            The input path to classify.

        Returns
        -------
        ``str``
            The classification of the input path to be used in normalisation.
        """

        # TODO: fix for string AND path rather than just string
        assert isinstance(input, str), "Input must be a string or Path object."

        text = input.strip()
        if not text:
            raise ValueError("Input path cannot be empty or whitespace.")

        if WINDOWS_DRIVE_RE.match(text):
            return "local str"

        parsed = urlparse(text)
        if parsed.scheme:
            if parsed.scheme == "file":
                return "local uri"
            return "remote uri"

        try:
            Path(text)
            return "local str"
        except Exception:
            pass

        raise ValueError(f"Input path {input} is not a valid local path or URI.")

    @staticmethod
    def _normalisation(input: Path | str) -> str:
        """
        Normalise the input path to a URI format before coersion into a FileSystemSetUp
        object.

        Parameters
        ----------
        ``input`` : Path | str
            The input path to normalise.

        Returns
        -------
        ``str``
            The normalised URI string.
        """
        if isinstance(input, Path):
            input = input.expanduser()
            input = input.resolve()
            assert input.is_absolute(), "Path must be absolute."
            return input.as_uri()

        if not isinstance(input, str):
            raise TypeError(
                f"Input must be a string or Path object. {input} is of type {type(input)}."
            )

        input = input.strip()

        classification = FileSystemSetUp._classification(input)

        if classification == "local str":
            input = Path(input).expanduser()
            input = input.resolve()
            assert input.is_absolute(), "Path must be absolute."
            return input.as_uri()

        elif classification == "local uri" or classification == "remote uri":
            return input.strip()

        else:
            raise ValueError(f"Unknown classification for input: {input}")

    @staticmethod
    def _uri_to_parts(uri: str, type: str) -> tuple[str, str, str | None, str | None]:
        """
        Convert a URI into:
        (prefix, root, workspace_path, file_name)

        Parameters
        ----------
        ``uri`` : str
            The URI string to parse.

        Returns
        -------
        ``tuple[str, str, str | None, str | None]``
            A tuple containing the prefix, root, workspace path, and file name.

        Raises
        ------
        ``ValueError``
            If the URI does not contain a scheme.
        """
        parsed = urlsplit(uri)
        if not parsed.scheme:
            raise ValueError(f"Expected URI with scheme, got: {uri!r}")

        prefix = f"{parsed.scheme}:///"

        # Decode escaped characters and split path robustly
        raw_path = unquote(parsed.path or "")
        path_parts = [p for p in PurePosixPath(raw_path).parts if p not in ("/", "")]

        # file:// handling
        if parsed.scheme == "file":
            # Windows file URI: file:///C:/...
            if path_parts and path_parts[0].endswith(":"):
                root = path_parts[0] + "/"  # C:/
                tail = path_parts[1:]
            # UNC form: file://server/share/...
            elif parsed.netloc:
                if path_parts:
                    root = f"//{parsed.netloc}/{path_parts[0]}"
                    tail = path_parts[1:]
                else:
                    root = f"//{parsed.netloc}"
                    tail = []
            # POSIX form: file:///home/...
            else:
                root = "/"
                tail = path_parts
        else:
            # Cloud URIs like s3://bucket/key...
            root = parsed.netloc
            tail = path_parts

        file_name = None if type == "dir" else (tail[-1] if tail else None)
        workspace_path = "/".join(tail[:-1] if file_name else tail) or None
        return prefix, root, workspace_path, file_name

    @classmethod
    def confirm_typing(cls, input: Any, path_type: str):
        if isinstance(input, FileSystemSetUp):
            return input
        elif isinstance(input, (str, Path)):
            return cls.from_any(input, path_type=path_type)
        else:
            raise TypeError(
                f"Input must be a string, Path, or FileSystemSetUp object. {input} is of type {type(input)}."
            )


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
    ) -> str: ...

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

    def join_path(
        self,
        *paths: str,
    ) -> str | Path: ...

    def suffix(
        self,
    ) -> str: ...

    def stem(
        self,
        type: str,  # dir or data
    ) -> str: ...

    def write_text(
        self,
        content: str,
        encoding: str = "utf-8",
    ) -> None: ...


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
    ) -> str:
        """
        Expands the user tilde (~) in the path.

        Returns
        -------
        ``Path``
            The path with the user tilde expanded.
        """
        return (
            str(self.data_path.expanduser())
            if self.data_path
            else str(self.dir_path.expanduser())
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

    def join_path(
        self,
        *paths: str,
    ) -> Path:
        """
        Join multiple path components into a single path.

        Parameters
        ----------
        ``*paths`` : str
            The path components to join.

        Returns
        -------
        ``str``
            The joined path as a string.
        """
        return self.dir_path.joinpath(*paths)

    def suffix(self) -> str:
        """
        Get the suffix of the data file.

        Returns
        -------
        ``str``
            The suffix of the data file, or an empty string if the data path is not set.
        """
        return self.data_path.suffix if self.data_path else ""

    def stem(self, type: str) -> str:
        """
        Returns the stem of the path, which is the final component of the path without
        its suffix.

        Returns
        -------
        ``str``
            The stem of the path corresponding to the specified type ('dir' or 'data'),
            or an empty string if the path is not set.
        """
        if type == "dir":
            return self.dir_path.stem if self.dir_path else ""
        elif type == "data":
            return self.data_path.stem if self.data_path else ""
        else:
            raise ValueError("Invalid type. Expected 'dir' or 'data'.")

    def write_text(
        self,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """
        Write text content to the data file.

        Parameters
        ----------
        ``content`` : str
            The text content to write to the data file.
        ``encoding`` : str, optional
            The encoding to use for writing the text, by default "utf-8".
        """
        if not self.data_path:
            raise ValueError("Data path is not set. Cannot write text.")
        self.data_path.write_text(content, encoding=encoding)


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
            The prefix associated with the file system (e.g., 's3a://', 'file:///').
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
    def update_fs(
        cls, path: str | Path | FileSystemSetUp, fs: FileSystem, path_type: str = "file"
    ) -> FileSystem:
        """
        Update the file system instance with a new setup.

        Parameters
        ----------
        ``path`` : str
            The path to the new setup information.
        ``fs`` : FileSystem
            The existing file system instance to update.
        ``path_type`` : str, optional
            The type of the file system, by default "file".

        Returns
        -------
        ``FileSystem``
            An updated instance of the appropriate file system class.
        """
        setup = FileSystemSetUp.confirm_typing(path, path_type=path_type)
        fs = cls.create(setup)
        return fs


# Registering the file system classes with their respective prefixes
FileSystemFactory.register("file:///", LocalFileSystem)
