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


class TestS3Functions:
    def test_exists(self, s3_file_system, s3):
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )

        assert s3_file_system.exists(type="data") is True
        assert s3_file_system.exists(type="dir") is True

    def test_not_exists(self, s3_file_system, s3):
        s3.create_bucket(Bucket="my-test-bucket")

        assert s3_file_system.exists(type="data") is False
        assert s3_file_system.exists(type="dir") is False

    def test_file_not_exists_dir_exists(self, s3_file_system, s3):
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/",
        )

        assert s3_file_system.exists(type="data") is False
        assert s3_file_system.exists(type="dir") is True

    def test_exists_invalid_type(self, s3_file_system, s3):
        with pytest.raises(ValueError):
            s3_file_system.exists(type="invalid_type")

    def test_exists_error_typing(self, s3_file_system, s3):
        import botocore.exceptions

        with pytest.raises(botocore.exceptions.ClientError):
            s3_file_system.exists(type="data")

    def test_no_file_name_error(self, s3):
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
