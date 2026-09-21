import pytest
from moto import mock_aws

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # pragma: allowlist secret
    # secret allowed as this is a fake key for mocking/testing purposes only
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def s3_filesystem_setup():
    """Fixture to set up a mocked S3 file system."""
    return FileSystemSetUp(
        prefix="s3://",
        root="my-test-bucket",
        workspace_path="test_folder",
        file_name="test.txt",
    )


@pytest.fixture
def s3_file_system(s3_filesystem_setup):
    """Fixture to provide an S3FileSystem instance."""
    return FileSystemFactory.create(s3_filesystem_setup)


@pytest.fixture
def s3(aws_credentials):
    """Fixture to provide a mocked S3 resource."""
    with mock_aws():
        import boto3

        yield boto3.client("s3")


class TestS3FunctionsExists:
    def test_exists(self, s3_file_system, s3):
        """
        Tests that the exists method correctly identifies the
        existence of a file and a directory in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )

        assert s3_file_system.exists(type="data") is True
        assert s3_file_system.exists(type="dir") is True

    def test_not_exists(self, s3_file_system, s3):
        """
        Tests that the exists method correctly identifies the non-existence of a
        file and a directory in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")

        assert s3_file_system.exists(type="data") is False
        assert s3_file_system.exists(type="dir") is False

    def test_file_not_exists_dir_exists(self, s3_file_system, s3):
        """
        Tests that the exists method correctly identifies non-existence of a file
        and existence of a directory in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/",
        )

        assert s3_file_system.exists(type="data") is False
        assert s3_file_system.exists(type="dir") is True

    def test_exists_invalid_type(self, s3_file_system):
        """
        Tests that the exists method raises a ValueError when an invalid type is specified.
        """
        with pytest.raises(ValueError):
            s3_file_system.exists(type="invalid_type")

    def test_exists_error_typing(self, s3_file_system):
        """
        Tests that the exists method raises a ClientError when there is an error
        accessing the S3 file system.
        """
        import botocore.exceptions

        with pytest.raises(botocore.exceptions.ClientError):
            s3_file_system.exists(type="data")

    def test_no_file_name_error(self, s3):
        """
        Tests that a Value error is raised by the exists method when the file_name is
        None and a data path has been requested.
        """
        setup = FileSystemSetUp(
            prefix="s3://",
            root="my-test-bucket",
            workspace_path="test_folder",
            file_name=None,
        )
        s3_file_system = FileSystemFactory.create(setup)
        s3.create_bucket(Bucket="my-test-bucket")
        with pytest.raises(ValueError):
            s3_file_system.exists(type="data")

    def test_exists_no_key(self, s3_file_system, s3):
        """
        Tests that a Value error is raised by the exists method when the data_path is
        set to the bucket root.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3_file_system.data_path = "s3://my-test-bucket/"
        with pytest.raises(ValueError):
            s3_file_system.exists(type="data")
        s3_file_system.data_path = "s3://my-test-bucket/"
        with pytest.raises(ValueError):
            s3_file_system.exists(type="data")


class TestS3FunctionsIsAbsolute:
    def test_is_absolute(self, s3_file_system):
        """
        Tests that the is_absolute method correctly identifies an absolute path.
        """
        assert s3_file_system.is_absolute(type="dir") is True
        assert s3_file_system.is_absolute(type="data") is True

    def test_is_not_absolute(self):
        """
        Tests that the is_absolute method correctly identifies a non-absolute path.
        """
        setup = FileSystemSetUp(
            prefix="s3://",
            root="my-test-bucket",
            workspace_path="test_folder",
            file_name="test.txt",
        )
        fs_no_absolute = FileSystemFactory.create(setup)
        fs_no_absolute.dir_path = "s3://not-a-test-bucket"
        fs_no_absolute.data_path = "s3://not-a-test-bucket/test_folder/test.txt"
        assert fs_no_absolute.is_absolute(type="dir") is False
        assert fs_no_absolute.is_absolute(type="data") is False

    def test_is_absolute_invalid_type(self, s3_file_system):
        """
        Tests that the is_absolute method raises a ValueError when an invalid type is specified.
        """
        with pytest.raises(ValueError):
            s3_file_system.is_absolute(type="invalid_type")

    def test_is_absolute_errors(self, s3_file_system):
        """
        Tests that the is_absolute method raises a ValueError when the directory
        or data paths are None.
        """
        s3_file_system.dir_path = None
        s3_file_system.data_path = None

        with pytest.raises(ValueError):
            s3_file_system.is_absolute(type="dir")

        with pytest.raises(ValueError):
            s3_file_system.is_absolute(type="data")


class TestS3FunctionsIsFile:
    def test_is_file(self, s3_file_system, s3):
        """
        Tests that the is_file method correctly identifies a file in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )

        assert s3_file_system.is_file() is True

    def test_is_not_file(self, s3_file_system, s3):
        """
        Tests that the is_file method correctly identifies a non-file in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")

        # If file doesn't exists
        assert s3_file_system.is_file() is False

        # If the data_path ends with "/"
        s3_file_system.data_path = "s3://my-test-bucket/test_folder/"
        assert s3_file_system.is_file() is False

        # If there is no data_path in the file system
        s3_file_system.data_path = None
        assert s3_file_system.is_file() is False


class TestS3FunctionsSuffix:
    def test_suffix(self, s3_file_system):
        """
        Tests that the suffix method correctly extracts the file extension from the data_path.
        """
        s3_file_system.data_path = "s3://my-test-bucket/test_folder/test.txt"
        assert s3_file_system.suffix() == ".txt"

    def test_suffix_no_data_path(self, s3_file_system):
        """
        Tests that the suffix method raises a ValueError when the data_path is None.
        """
        s3_file_system.data_path = None
        with pytest.raises(ValueError):
            s3_file_system.suffix()


class TestS3FunctionsStem:
    def test_stem(self, s3_file_system):
        """
        Tests that the stem method correctly extracts the file name without extension
        from the data_path and dir_path.
        """
        s3_file_system.data_path = "s3://my-test-bucket/test_folder/test.txt"
        assert s3_file_system.stem(type="data") == "test"
        s3_file_system.dir_path = "s3://my-test-bucket/test_folder"
        assert s3_file_system.stem(type="dir") == "test_folder"

    def test_stem_no_data_path(self, s3_file_system):
        """
        Tests that the stem method raises a ValueError when the data_path is None.
        """
        s3_file_system.data_path = None
        with pytest.raises(ValueError):
            s3_file_system.stem(type="data")

        s3_file_system.dir_path = None
        with pytest.raises(ValueError):
            s3_file_system.stem(type="dir")


class TestS3FunctionsJoinPath:
    def test_join_path(self, s3_file_system):
        """
        Tests that the join_path method correctly joins the dir_path and file_name
        to form a complete data_path.
        """
        s3_file_system.dir_path = "s3://my-test-bucket/test_folder"
        expected_data_path = "s3://my-test-bucket/test_folder/test.txt"
        assert s3_file_system.join_path("test.txt") == expected_data_path

    def test_join_path_no_dir_path(self, s3_file_system):
        """
        Tests that the join_path method raises a ValueError when the dir_path is None.
        """
        s3_file_system.dir_path = None
        with pytest.raises(ValueError):
            s3_file_system.join_path("test.txt")

    def test_join_path_multiple(self, s3_file_system):
        """
        Tests that the join_path method correctly joins the dir_path and file_name
        to form a complete data_path.
        """
        s3_file_system.dir_path = "s3://my-test-bucket/test_folder"
        expected_data_path = "s3://my-test-bucket/test_folder/test_subfolder/test.txt"
        assert (
            s3_file_system.join_path("test_subfolder", "test.txt") == expected_data_path
        )


class TestS3FunctionsResolve:
    def test_resolve(self, s3_file_system):
        """
        Tests that the resolve method correctly returns the absolute path of the data_path.
        """
        s3_file_system.data_path = "s3://my-test-bucket/test_folder/test.txt"
        assert s3_file_system.resolve(type="data") == s3_file_system.data_path

        s3_file_system.dir_path = "s3://my-test-bucket/test_folder/"
        assert s3_file_system.resolve(type="dir") == s3_file_system.dir_path

    def test_resolve_no_data_path(self, s3_file_system):
        """
        Tests that the resolve method raises a ValueError when the data_path is None
        or when it does not contain the prefix.
        """
        s3_file_system.data_path = None
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="data")

        s3_file_system.data_path = "my-test-bucket/test_folder/test.txt"
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="data")

        s3_file_system.data_path = "s3://test_folder/test.txt"
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="data")

    def test_resolve_no_dir_path(self, s3_file_system):
        """
        Tests that the resolve method raises a ValueError when the dir_path is None
        or when it does not contain the prefix.
        """
        s3_file_system.dir_path = None
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="dir")

        s3_file_system.dir_path = "my-test-bucket/test_folder/"
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="dir")

        s3_file_system.dir_path = "s3://test_folder/"
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="dir")

    def test_resolve_invalid_type(self, s3_file_system):
        """
        Tests that the resolve method raises a ValueError when an invalid type is specified.
        """
        with pytest.raises(ValueError):
            s3_file_system.resolve(type="invalid_type")
