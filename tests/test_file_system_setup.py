from pathlib import Path

import pytest

from onsrap.errors import FileSystemSetUpError, PathTypeError
from onsrap.file_system_setup import (
    FileSystemFactory,
    FileSystemSetUp,
    S3FileSystem,
)

"""
This file exists to test S3 implementation however these tests will not run
unless you have access to an S3 bucket and have set up your AWS credentials correctly.

This information is not logged in the repository and therefore developers will need to
add their own credentials/information when these tests are run. For this reason, any
tests that require a spark session or access to S3 are skipped by default.
"""

MY_BUCKET = "my-test-bucket"
SPARK = None


@pytest.fixture
def s3_file_real():
    return FileSystemSetUp(
        prefix="s3a://",
        root=MY_BUCKET,
        workspace_path="test_workspace",
        file_name="test_file.csv",
        spark_session=SPARK,
    )


@pytest.fixture
def s3_file_not_real():
    return FileSystemSetUp(
        prefix="s3a://",
        root=MY_BUCKET,
        workspace_path="test_workspace",
        file_name="not_a_test_file.csv",
        spark_session=SPARK,
    )


class TestFileSystemSetUp:
    def test_create_uri(self, s3_file_real):
        """
        Test that checks all possible routes for uri creation based on
        parameters in FileSystemSetUp object.
        """
        uri = s3_file_real.create_uri()
        assert uri == f"s3a://{MY_BUCKET}/test_workspace/test_file.csv"

        s3_file_real.file_name = None
        uri_no_file = s3_file_real.create_uri()
        assert uri_no_file == f"s3a://{MY_BUCKET}/test_workspace"

        s3_file_real.file_name = "test_file.csv"
        s3_file_real.workspace_path = None
        uri_no_workspace = s3_file_real.create_uri()
        assert uri_no_workspace == f"s3a://{MY_BUCKET}/test_file.csv"

        s3_file_real.file_name = None
        uri_no_workspace_no_file = s3_file_real.create_uri()
        assert uri_no_workspace_no_file == f"s3a://{MY_BUCKET}"

    def test_from_str_norm(
        self,
    ):
        """
        Test that checks the from_str_norm method of FileSystemSetUp class.
        """
        s3_file_real_str = "s3a://my-test-bucket/test_workspace/test_file.csv"
        s3_file_real_from_str = FileSystemSetUp.from_str(s3_file_real_str)
        assert isinstance(s3_file_real_from_str, FileSystemSetUp)
        assert s3_file_real_from_str.prefix == "s3a://"
        assert s3_file_real_from_str.root == "my-test-bucket"
        assert s3_file_real_from_str.workspace_path == "test_workspace"
        assert s3_file_real_from_str.file_name == "test_file.csv"

    @pytest.mark.skip(reason="Requires spark and S3 access to run")
    def test_from_str_hive(
        self,
    ):
        """
        Test that checks string files in a Hive format are correctly distilled
        into a FileSystemSetUp object.
        """
        hive_str = "database_name.table_name"
        from_str = FileSystemSetUp.from_str(hive_str, spark_session=SPARK)

        assert isinstance(from_str, FileSystemSetUp)
        assert from_str.prefix == "s3a://"
        assert from_str.root == MY_BUCKET
        assert from_str.workspace_path == FileSystemSetUp._extract_db_fpath(
            SPARK, "database_name"
        )
        assert from_str.file_name == "table_name"

    def test_from_path(
        self,
    ):
        """
        Test that checks the from_path method of FileSystemSetUp class.
        """
        path = Path("C://my_project/my_folder/my_file.py")
        from_path = FileSystemSetUp.from_path(path)
        assert isinstance(from_path, FileSystemSetUp)
        assert from_path.prefix == "file:///"
        assert from_path.root == "C:/"
        assert from_path.workspace_path == "my_project/my_folder"
        assert from_path.file_name == "my_file.py"

    def test_from_any(
        self,
    ):
        """
        Test that checks the from_any method of FileSystemSetUp class.
        """
        s3_file_real_str = "s3a://my-test-bucket/test_workspace/test_file.csv"
        from_any_str = FileSystemSetUp.from_any(s3_file_real_str)
        assert isinstance(from_any_str, FileSystemSetUp)
        assert from_any_str == FileSystemSetUp.from_str(s3_file_real_str)

        path = Path("C://my_project/my_folder/my_file.py")
        from_any_path = FileSystemSetUp.from_any(path)
        assert isinstance(from_any_path, FileSystemSetUp)
        assert from_any_path == FileSystemSetUp.from_path(path)

        path = None
        with pytest.raises(FileSystemSetUpError):
            FileSystemSetUp.from_any(path)

    def test_file_system_setup_factory(self, s3_file_real):
        """
        Test that checks the FileSystemFactory method and ensures that it branches
        to the correct routes.
        """
        s3_fs = FileSystemSetUp.file_system_setup_factory(
            s3_file_real, path_type="file"
        )
        assert isinstance(s3_fs, FileSystemSetUp)

        s3_file_real_str = "s3a://my-test-bucket/test_workspace/test_file.csv"
        s3_fs = FileSystemSetUp.file_system_setup_factory(
            s3_file_real_str, path_type="file"
        )
        assert isinstance(s3_fs, FileSystemSetUp)
        assert s3_fs == FileSystemSetUp.from_str(s3_file_real_str)

        path = Path("C://my_project/my_folder/my_file.py")
        path_fs = FileSystemSetUp.file_system_setup_factory(path, path_type="file")
        assert path_fs == FileSystemSetUp.from_path(path, path_type="file")
        assert isinstance(path_fs, FileSystemSetUp)

        path = None
        with pytest.raises(TypeError):
            FileSystemSetUp.file_system_setup_factory(path, path_type="dir")

    def test_classification_method(
        self,
    ):
        """
        Test that checks the classification method of FileSystemSetUp class.
        """
        string = 11
        with pytest.raises(AssertionError):
            FileSystemSetUp._classification(string)

        string = "   "
        with pytest.raises(FileSystemSetUpError):
            FileSystemSetUp._classification(string)

        string = "C://my_project/my_folder/my_file.py"
        assert FileSystemSetUp._classification(string) == "local str"

        string = "s3a://my-test-bucket/test_workspace/test_file.csv"
        assert FileSystemSetUp._classification(string) == "remote uri"

        string = "file:///my_project/my_folder/my_file.py"
        assert FileSystemSetUp._classification(string) == "local uri"

        string = "folder/file_name.py"
        assert FileSystemSetUp._classification(string) == "local str"

    def test_normalisation(
        self,
    ):
        """
        Test that checks the normalisation method of FileSystemSetUp class.
        """
        path = Path("folder/file_name.py")
        path_resolved = path.expanduser().resolve()
        path_uri = path_resolved.as_uri()

        assert FileSystemSetUp._normalisation(path) == path_uri

        path_str = "folder/file_name.py"
        assert FileSystemSetUp._normalisation(path_str) == path_uri

        string = "s3a://my-test-bucket/test_workspace/test_file.csv   "
        string_cleaned = "s3a://my-test-bucket/test_workspace/test_file.csv"
        assert FileSystemSetUp._normalisation(string) == string_cleaned

        with pytest.raises(TypeError):
            FileSystemSetUp._normalisation(11)

    def test_create_path(self, monkeypatch):
        """
        Test that checks the create_path method of FileSystemSetUp class.
        """
        path = FileSystemSetUp(
            prefix="s3a://",
            root=MY_BUCKET,
            workspace_path="test_workspace",
            file_name="test_file.csv",
            spark_session=SPARK,
        )

        assert path.create_path() is None

        path = FileSystemSetUp(
            prefix="file:///",
            root="my_project",
            workspace_path="my_folder",
            file_name="test_file.csv",
            spark_session=None,
        )

        assert path.create_path() is None

        monkeypatch.setattr(Path, "exists", lambda self: True)
        assert path.create_path() == Path("my_project/my_folder/test_file.csv")

        path.workspace_path = None
        assert path.create_path() == Path("my_project/test_file.csv")

        path.workspace_path = "my_folder"
        path.file_name = None
        assert path.create_path() == Path("my_project/my_folder")

        path.workspace_path = None
        assert path.create_path() == Path("my_project")

    def test_uri_to_parts(self):
        """
        Tests the uri_to_parts method of FileSystemSetUp class.
        """

        uri = "s3a://my-test-bucket/test_workspace/test_file.csv"
        parts = FileSystemSetUp._uri_to_parts(uri, type="file")
        assert parts[0] == "s3a://"
        assert parts[1] == "my-test-bucket"
        assert parts[2] == "test_workspace"
        assert parts[3] == "test_file.csv"

        file_uri = "file:///my_project/my_folder/my_subfolder/my_file.py"
        parts = FileSystemSetUp._uri_to_parts(file_uri, type="file")
        assert parts[0] == "file:///"
        assert parts[1] == "/"
        assert parts[2] == "my_project/my_folder/my_subfolder"
        assert parts[3] == "my_file.py"

        parts = FileSystemSetUp._uri_to_parts(file_uri, type="dir")
        assert parts[3] is None


class TestS3FileSystem:
    def test_s3_file_system_creation(self, s3_file_real):
        """
        Tests that the FileSystemFactory correctly creates an S3FileSystem object
        when provided with a FileSystemSetUp object that has an S3 URI.
        """
        s3_fs = FileSystemFactory.create(s3_file_real)
        assert isinstance(s3_fs, S3FileSystem)

    @pytest.mark.skip(reason="Requires spark and S3 access to run")
    def test_exists_dir(self, s3_file_real, s3_file_not_real):
        """
        Tests that the exists method of S3FileSystem correctly identifies whether
        a directory exists or not based on the provided FileSystemSetUp object.
        """
        s3_fs = FileSystemFactory.create(s3_file_real)
        assert s3_fs.exists(type="dir") is True

        s3_fs.dir_path = None
        with pytest.raises(FileSystemSetUpError):
            s3_fs.exists(type="dir")

        s3_fs_not_real = FileSystemFactory.create(s3_file_not_real)
        assert s3_fs_not_real.exists(type="dir") is False

    @pytest.mark.skip(reason="Requires spark and S3 access to run")
    def test_exists_file(self, s3_file_real, s3_file_not_real):
        """
        Tests that the exists method of S3FileSystem correctly identifies whether
        a file exists or not based on the provided FileSystemSetUp object.
        """
        s3_fs = FileSystemFactory.create(s3_file_real)
        assert s3_fs.exists(type="data") is True

        s3_fs.data_path = None
        with pytest.raises(FileSystemSetUpError):
            s3_fs.exists(type="data")

        s3_fs_not_real = FileSystemFactory.create(s3_file_not_real)
        assert s3_fs_not_real.exists(type="data") is False

    @pytest.mark.skip(reason="Requires spark and S3 access to run")
    def test_exists_errors(self, s3_file_real):
        """
        Tests that the exists method of S3FileSystem raises a PathTypeError
        when provided with an invalid type or errors when the dir_path/data_path
        is the bucket.
        """
        s3_fs = FileSystemFactory.create(s3_file_real)

        with pytest.raises(PathTypeError):
            s3_fs.exists(type="invalid_type")

        s3_fs.dir_path = f"s3a://{MY_BUCKET}"
        with pytest.raises(FileSystemSetUpError):
            s3_fs.exists(type="dir")

        s3_fs.data_path = f"s3a://{MY_BUCKET}"
        with pytest.raises(FileSystemSetUpError):
            s3_fs.exists(type="data")
