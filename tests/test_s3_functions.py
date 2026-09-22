import botocore
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


class TestS3FunctionsReadText:
    def test_read_text(self, s3_file_system, s3):
        """
        Tests that the read_text method correctly reads the content of a file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )

        content = s3_file_system.read_text()
        assert content == "Test content"

    def test_read_text_blank_files(self, s3_file_system, s3):
        """
        Tests that the read_text method correctly reads the content of a file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"")

        content = s3_file_system.read_text()
        assert content == ""

    def test_read_text_diff_encoding(self, s3_file_system, s3):
        """
        Tests that the read_text method correctly reads the content of a file
        in the mocked S3 file system with a different encoding than the default "utf-8".
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/test.txt",
            Body="Test content with special char: ñ".encode("latin-1"),
        )

        content = s3_file_system.read_text(encoding="latin-1")
        assert content == "Test content with special char: ñ"

    def test_read_text_no_file(self, s3_file_system, s3):
        """
        Tests that the read_text method raises a ClientError when trying to read
        a non-existent file in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")

        with pytest.raises(FileNotFoundError):
            s3_file_system.read_text()

    def test_read_text_no_data_path(self, s3_file_system):
        """
        Tests that the read_text method raises a ValueError when the data_path is None.
        """
        s3_file_system.data_path = None
        with pytest.raises(ValueError):
            s3_file_system.read_text()

    def test_non_matching_encoding(self, s3_file_system, s3):
        """
        Tests that the read_text method raises a UnicodeDecodeError when trying to read
        a file with an encoding that does not match the file's actual encoding.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/test.txt",
            Body="Test content with special char: ñ".encode("latin-1"),
        )

        with pytest.raises(UnicodeDecodeError):
            s3_file_system.read_text(encoding="utf-8")

    def test_read_text_large_file(self, s3_file_system, s3):
        """
        Tests that the read_text method correctly reads the content of a large file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        large_content = "A" * 2 * 1024 * 1024  # 2 MB of 'A's
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/large_test.txt",
            Body=large_content.encode("utf-8"),
        )

        s3_file_system.data_path = "s3://my-test-bucket/test_folder/large_test.txt"
        content = s3_file_system.read_text()
        assert content == large_content

    def test_read_text_invalid_data_path(self, s3_file_system, s3):
        """
        Tests that the read_text method raises a ValueError when the data_path is invalid.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )
        s3_file_system.data_path = "s3://my-test-bucket/"
        with pytest.raises(ValueError):
            s3_file_system.read_text()


class TestS3FunctionsWriteText:
    def test_write_text(self, s3_file_system, s3):
        """
        Tests that the write_text method correctly writes content to a file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        content_to_write = "This is a test content."

        s3_file_system.write_text(content_to_write)

        # Verify that the content was written correctly
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        written_content = response["Body"].read().decode("utf-8")
        assert written_content == content_to_write

    def test_write_overwriting(self, s3_file_system, s3):
        """
        Tests that the write_text method correctly overwrites existing content
        in a file in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        initial_content = "Initial content."
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/test.txt",
            Body=initial_content.encode("utf-8"),
        )

        new_content = "New content to overwrite."
        s3_file_system.write_text(new_content)

        # Verify that the content was overwritten correctly
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        written_content = response["Body"].read().decode("utf-8")
        assert written_content == new_content

    def test_write_no_content(self, s3_file_system, s3):
        """
        Tests that the write_text method correctly writes an empty string to a file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        empty_content = ""

        s3_file_system.write_text(empty_content)

        # Verify that the content was written correctly
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        written_content = response["Body"].read().decode("utf-8")
        assert written_content == empty_content

    def test_write_large_files(self, s3_file_system, s3):
        """
        Tests that the write_text method correctly writes a large content to a file
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        large_content = "B" * 2 * 1024 * 1024  # 2 MB of 'B's

        with s3_file_system.open(mode="w", encoding="utf-8") as file:
            file.write(large_content)

        # Verify that the content was written correctly
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        written_content = response["Body"].read().decode("utf-8")
        assert written_content == large_content

    def test_write_text_no_data_path(self, s3_file_system):
        """
        Tests that the write_text method raises a ValueError when the data_path is None.
        """
        s3_file_system.data_path = None
        with pytest.raises(ValueError):
            s3_file_system.write_text("Some content")

    def test_write_text_invalid_data_path(self, s3_file_system):
        """
        Tests that the write_text method raises a ValueError when the data_path is invalid.
        """
        s3_file_system.data_path = "s3://my-test-bucket/"
        with pytest.raises(ValueError):
            s3_file_system.write_text("Some content")


class TestS3FunctionsOpen:
    def test_open_read_mode(self, s3_file_system, s3):
        """
        Tests that the open method correctly opens a file in read mode
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        content_to_write = "This is a test content."
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/test.txt",
            Body=content_to_write.encode("utf-8"),
        )

        with s3_file_system.open(mode="r", encoding="utf-8") as file:
            read_content = file.read()
            assert read_content == content_to_write

    def test_open_write_mode(self, s3_file_system, s3):
        """
        Tests that the open method correctly opens a file in write mode
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        content_to_write = "This is a test content."

        with s3_file_system.open(mode="w", encoding="utf-8") as file:
            file.write(content_to_write)

        # Verify that the content was written correctly
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        written_content = response["Body"].read().decode("utf-8")
        assert written_content == content_to_write

    def test_open_readlines(self, s3_file_system, s3):
        """
        Tests that the open method correctly opens a file in read mode
        and reads lines one by one in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        content_to_write = "Line 1\nLine 2\nLine 3"
        s3.put_object(
            Bucket="my-test-bucket",
            Key="test_folder/test.txt",
            Body=content_to_write.encode("utf-8"),
        )

        with s3_file_system.open(mode="r", encoding="utf-8") as file:
            lines = file.readlines()
            assert lines == ["Line 1\n", "Line 2\n", "Line 3"]

    def test_open_text_wrapper_encoding_property(self, s3_file_system, s3):
        """
        Tests that the file object returned in text mode has the encoding property.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=b"Test content"
        )

        # Test default encoding
        with s3_file_system.open(mode="r") as f:
            assert hasattr(f, "encoding")
            assert f.encoding in ["utf-8", "UTF-8"]  # Handle case variations

        # Test custom encoding
        with s3_file_system.open(mode="r", encoding="latin-1") as f:
            assert hasattr(f, "encoding")
            assert f.encoding.lower() == "latin-1"

    def test_open_seek_tell_binary_mode(self, s3_file_system, s3):
        """
        Tests that seek and tell operations work correctly in binary mode.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        test_content = b"0123456789"
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/test.txt", Body=test_content
        )

        with s3_file_system.open(mode="rb") as f:
            # Read first 5 bytes
            chunk1 = f.read(5)
            assert chunk1 == b"01234"

            # Check current position
            pos = f.tell()
            assert pos == 5

            # Seek back to start
            f.seek(0)
            pos = f.tell()
            assert pos == 0

            # Verify we can read from start again
            chunk_from_start = f.read(3)
            assert chunk_from_start == b"012"

    def test_open_context_manager_upload_timing(self, s3_file_system, s3):
        """
        Tests that content is only uploaded to S3 after the context manager exits.
        """
        s3.create_bucket(Bucket="my-test-bucket")

        # Verify file doesn't exist yet
        with pytest.raises(
            (FileNotFoundError, botocore.exceptions.ClientError)
        ):  # FileNotFoundError or NoSuchKey error
            s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")

        # Open and write within context
        with s3_file_system.open(mode="w") as f:
            f.write("Content being written")

            # File should still not exist in S3 while inside context
            with pytest.raises((FileNotFoundError, botocore.exceptions.ClientError)):
                s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")

        # After exiting context, file should exist
        response = s3.get_object(Bucket="my-test-bucket", Key="test_folder/test.txt")
        content = response["Body"].read().decode("utf-8")
        assert content == "Content being written"


class TestS3FunctionsGlob:
    def test_glob(self, s3_file_system, s3):
        """
        Tests that the glob method correctly lists files matching a pattern
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file1.txt", Body=b"File 1"
        )
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file2.txt", Body=b"File 2"
        )
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file3.log", Body=b"File 3"
        )

        # List all .txt files
        txt_files = s3_file_system.glob("*.txt")
        expected_txt_files = [
            "s3://my-test-bucket/test_folder/file1.txt",
            "s3://my-test-bucket/test_folder/file2.txt",
        ]
        assert set(txt_files) == set(expected_txt_files)
        for i in txt_files:
            assert i.startswith("s3://my-test-bucket/test_folder/")

    def test_glob_no_matching_files(self, s3_file_system, s3):
        """
        Tests that the glob method returns an empty list when no files match the pattern.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file1.log", Body=b"File 1"
        )

        # List all .txt files (none exist)
        txt_files = s3_file_system.glob("*.txt")
        assert txt_files == []

    def test_glob_case_sensitive(self, s3_file_system, s3):
        """
        Tests that the glob method is case-sensitive when matching file patterns.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/File1.TXT", Body=b"File 1"
        )
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file2.txt", Body=b"File 2"
        )

        # List all .txt files (should only match lowercase)
        txt_files = s3_file_system.glob("*.txt")
        expected_txt_files = ["s3://my-test-bucket/test_folder/file2.txt"]
        assert set(txt_files) == set(expected_txt_files)

    def test_glob_ignores_objects_outside_prefix(self, s3_file_system, s3):
        """
        Tests that the glob method ignores objects that are outside the specified prefix.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/file1.txt", Body=b"File 1"
        )
        s3.put_object(
            Bucket="my-test-bucket", Key="other_folder/file2.txt", Body=b"File 2"
        )

        # List all .txt files in test_folder (should ignore other_folder)
        txt_files = s3_file_system.glob("*.txt")
        expected_txt_files = ["s3://my-test-bucket/test_folder/file1.txt"]
        assert set(txt_files) == set(expected_txt_files)

    def test_glob_with_directory_marker_obj(self, s3_file_system, s3):
        """
        Tests that the glob method correctly handles directory marker objects in S3.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        # Create a directory marker object
        s3.put_object(Bucket="my-test-bucket", Key="test_folder/", Body=b"")
        s3.put_object(
            Bucket="my-test-bucket", Key="test_folder/sub_dir/file1.txt", Body=b"File 1"
        )

        # List all .txt files (should ignore the directory marker)
        txt_files = s3_file_system.glob("sub_dir/*.txt")
        expected_txt_files = ["s3://my-test-bucket/test_folder/sub_dir/file1.txt"]
        assert set(txt_files) == set(expected_txt_files)

    def test_glob_over_1000_matches(self, s3_file_system, s3):
        """
        Tests that the glob method correctly handles more than 1000 matching files
        in the mocked S3 file system.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        # Create 1500 files
        for i in range(1100):
            s3.put_object(
                Bucket="my-test-bucket",
                Key=f"test_folder/file_{i}.txt",
                Body=f"File {i}".encode("utf-8"),
            )

        # List all .txt files
        txt_files = s3_file_system.glob("*.txt")
        assert len(txt_files) == 1100

    def test_glob_over_1000_records_less_matches(self, s3_file_system, s3):
        """
        Tests that the glob method correctly handles more than 1000 files in S3
        but with fewer than 1000 matches for the specified pattern.
        """
        s3.create_bucket(Bucket="my-test-bucket")
        # Create 1500 files
        for i in range(1100):
            suffix = ".txt" if i % 10 == 0 else ".log"
            s3.put_object(
                Bucket="my-test-bucket",
                Key=f"test_folder/file_{i}{suffix}",
                Body=f"File {i}".encode("utf-8"),
            )

        # List all .txt files
        txt_files = s3_file_system.glob("*.txt")
        assert len(txt_files) == 110
