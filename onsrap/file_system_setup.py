from dataclasses import dataclass
from typing import Optional, Protocol


class FileSystem(Protocol):
    """
    A Protocol that defines methods for the package to interact with different
    file systems. This ensures that there are set methods in place for every file
    system that we expect an interaction with to allow seamless integration.
    """

    ...


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

    ...


# TODO: edit this docstring with whether Boto3 or Spark is used
class S3FileSystem:
    """
    A class that holds methods for interacting with the S3 file system.
    This class will utilise Boto3/Spark methodology to create, read, and write to
    the S3 file system.

    This class is part of the FileSystem Protocol.
    """

    ...


@dataclass
class FileSystemSetUp:
    """
    A class that holds information relevant to determining the file system being used.

    Parameters
    ----------
    ``prefix`` : str, default = "file://"
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

    root: str
    workspace_path: Optional[str] = None
    prefix: str = "file://"
