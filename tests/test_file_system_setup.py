from rap_toolkit.file_system_setup import FileSystemSetUp


def test_create_uri_preserves_percent_escaped_file_segments() -> None:
    uri = "file:///tmp/folder%20name/report%231.txt"

    setup = FileSystemSetUp.from_str(uri)

    assert setup.create_uri() == uri


def test_create_uri_preserves_percent_escaped_s3_segments() -> None:
    uri = "s3://example-bucket/path%20with%20space/report%23final.csv"

    setup = FileSystemSetUp.from_str(uri)

    assert setup.create_uri() == uri
