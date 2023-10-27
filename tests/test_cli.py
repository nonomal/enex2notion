import logging

import pytest
from requests import HTTPError

from enex2notion.cli import cli
from enex2notion.utils_exceptions import BadTokenException, NoteUploadFailException
from enex2notion.utils_static import Rules


@pytest.fixture()
def mock_api(mocker):
    return {
        "get_import_root": mocker.patch("enex2notion.cli_notion.get_import_root"),
        "get_notion_client": mocker.patch("enex2notion.cli_notion.get_notion_client"),
        "get_notebook_database": mocker.patch(
            "enex2notion.cli_upload.get_notebook_database"
        ),
        "get_notebook_page": mocker.patch("enex2notion.cli_upload.get_notebook_page"),
        "upload_note": mocker.patch("enex2notion.cli_upload.upload_note"),
        "parse_note": mocker.patch("enex2notion.cli_upload.parse_note"),
    }


@pytest.fixture()
def fake_note_factory(mocker):
    mock_count = mocker.patch("enex2notion.cli_upload.count_notes")
    mock_iter = mocker.patch("enex2notion.cli_upload.iter_notes")
    mock_iter.return_value = [mocker.MagicMock(note_hash="fake_hash", is_webclip=False)]
    mock_count.side_effect = lambda x: len(mock_iter.return_value)

    return mock_iter


def test_dry_run(mock_api, fake_note_factory):
    cli(["fake.enex"])

    mock_api["get_import_root"].assert_not_called()


def test_dir(mock_api, fake_note_factory, fs):
    fs.makedir("test_dir")
    fs.create_file("test_dir/test.enex")

    cli(["test_dir"])

    mock_api["parse_note"].assert_called_once()


def test_empty_dir(mock_api, fake_note_factory, fs):
    fs.makedir("test_dir")

    cli(["test_dir"])

    mock_api["upload_note"].assert_not_called()


def test_verbose(mock_api, fake_note_factory, mocker):
    fake_logs = {}
    mock_logger = mocker.patch("enex2notion.cli_logging.logging")
    mock_logger.getLogger = lambda name: fake_logs.setdefault(name, mocker.MagicMock())

    cli(["--verbose", "fake.enex"])

    mock_logger.basicConfig.assert_called_once_with(format=mocker.ANY)
    mock_logger.getLogger("enex2notion").setLevel.assert_called_with(mock_logger.DEBUG)


def test_no_verbose(mock_api, fake_note_factory, mocker):
    fake_logs = {}
    mock_logger = mocker.patch("enex2notion.cli_logging.logging")
    mock_logger.getLogger = lambda name: fake_logs.setdefault(name, mocker.MagicMock())

    cli(["fake.enex"])

    mock_logger.basicConfig.assert_called_once_with(format=mocker.ANY)
    mock_logger.getLogger("enex2notion").setLevel.assert_called_with(mock_logger.INFO)


def test_db_mode(mock_api, fake_note_factory, mocker):
    cli(["--token", "fake_token", "fake.enex"])

    mock_api["get_notebook_page"].assert_not_called()
    mock_api["get_notebook_database"].assert_called_once_with(mocker.ANY, "fake")


def test_page_mode(mock_api, fake_note_factory, mocker):
    cli(["--token", "fake_token", "--mode", "PAGE", "fake.enex"])

    mock_api["get_notebook_database"].assert_not_called()
    mock_api["get_notebook_page"].assert_called_once_with(mocker.ANY, "fake")


def test_upload_fail_retry(mock_api, fake_note_factory, mocker, caplog):
    mock_api["upload_note"].side_effect = [NoteUploadFailException] * 4 + [None]

    with caplog.at_level(logging.WARNING, logger="enex2notion"):
        cli(["--token", "fake_token", "fake.enex"])

    assert mock_api["upload_note"].call_count == 5
    assert "Failed to upload note" in caplog.text


def test_upload_fail_retry_custom(mock_api, fake_note_factory, mocker, caplog):
    retries = 10

    mock_api["upload_note"].side_effect = [NoteUploadFailException] * (retries * 2)

    with caplog.at_level(logging.ERROR, logger="enex2notion"):
        with pytest.raises(NoteUploadFailException):
            cli(
                [
                    "--token",
                    "fake_token",
                    "--retry",
                    str(retries),
                    "fake.enex",
                ]
            )

    assert mock_api["upload_note"].call_count == retries
    assert "Failed to upload note" in caplog.text


def test_upload_fail_retry_infinite(mock_api, fake_note_factory, mocker, caplog):
    retries = 0
    exceptions = [NoteUploadFailException] * 10

    mock_api["upload_note"].side_effect = exceptions + [None]

    with caplog.at_level(logging.WARNING, logger="enex2notion"):
        cli(["--token", "fake_token", "--retry", str(retries), "fake.enex"])

    assert mock_api["upload_note"].call_count == len(exceptions) + 1
    assert "Failed to upload note" in caplog.text


def test_upload_fail(mock_api, fake_note_factory, mocker, caplog):
    mock_api["upload_note"].side_effect = [NoteUploadFailException] * 5

    with pytest.raises(NoteUploadFailException):
        cli(["--token", "fake_token", "fake.enex"])


def test_upload_skip(mock_api, fake_note_factory, mocker, caplog):
    mock_api["upload_note"].side_effect = [NoteUploadFailException] * 5

    with caplog.at_level(logging.ERROR, logger="enex2notion"):
        cli(["--token", "fake_token", "--skip-failed", "fake.enex"])

    assert mock_api["upload_note"].call_count == 5
    assert "Failed to upload note" in caplog.text


def test_upload_notebook_fail(mock_api, fake_note_factory, mocker, caplog):
    mock_api["get_notebook_database"].side_effect = [NoteUploadFailException] * 5

    with pytest.raises(NoteUploadFailException):
        cli(["--token", "fake_token", "fake.enex"])


def test_upload_notebook_skip(mock_api, fake_note_factory, mocker, caplog):
    mock_api["get_notebook_database"].side_effect = [NoteUploadFailException] * 5

    with caplog.at_level(logging.ERROR, logger="enex2notion"):
        cli(["--token", "fake_token", "--skip-failed", "fake.enex"])

    assert mock_api["get_notebook_database"].call_count == 5
    assert "Failed to get notebook root for" in caplog.text


def test_no_keep_failed(mock_api, fake_note_factory, mocker):
    cli(["--token", "fake_token", "fake.enex"])

    mock_api["upload_note"].assert_called_once_with(
        mocker.ANY, mocker.ANY, mocker.ANY, False
    )


def test_keep_failed(mock_api, fake_note_factory, mocker):
    cli(["--token", "fake_token", "--keep-failed", "fake.enex"])

    mock_api["upload_note"].assert_called_once_with(
        mocker.ANY, mocker.ANY, mocker.ANY, True
    )


def test_add_meta(mock_api, fake_note_factory, mocker, parse_rules):
    cli(["--add-meta", "fake.enex"])

    parse_rules.add_meta = True

    mock_api["parse_note"].assert_called_once_with(mocker.ANY, parse_rules)


def test_skip_dupe(mock_api, fake_note_factory, mocker):
    cli(["--token", "fake_token", "fake.enex"])

    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash"),
        mocker.MagicMock(note_hash="fake_hash"),
    ]

    mock_api["upload_note"].assert_called_once()


def test_done_file(mock_api, fake_note_factory, mocker, fs):
    fs.create_file("done.txt")

    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash1", is_webclip=False),
        mocker.MagicMock(note_hash="fake_hash2", is_webclip=False),
    ]

    cli(["--token", "fake_token", "--done-file", "done.txt", "fake.enex"])

    with open("done.txt") as f:
        done_result = f.read()

    assert mock_api["upload_note"].call_count == 2
    assert done_result == "fake_hash1\nfake_hash2\n"


def test_done_file_populated(mock_api, fake_note_factory, mocker, fs):
    fs.create_file("done.txt", contents="fake_hash1\nfake_hash2\n")

    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash1"),
        mocker.MagicMock(note_hash="fake_hash2"),
    ]

    cli(["--token", "fake_token", "--done-file", "done.txt", "fake.enex"])

    mock_api["upload_note"].assert_not_called()


def test_done_file_empty(mock_api, fake_note_factory, fs):
    fake_note_factory.return_value = []

    cli(["--token", "fake_token", "--done-file", "done.txt", "fake.enex"])

    mock_api["upload_note"].assert_not_called()


def test_bad_file(mock_api, fake_note_factory):
    mock_api["parse_note"].return_value = []

    cli(["fake.enex"])

    mock_api["parse_note"].assert_called_once()


def test_webclip(mock_api, fake_note_factory, mocker, parse_rules):
    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash1", is_webclip=True),
    ]

    cli(["fake.enex"])

    mock_api["parse_note"].assert_called_once_with(mocker.ANY, parse_rules)


def test_webclip_pdf(mock_api, fake_note_factory, mocker, parse_rules):
    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash1", is_webclip=True),
    ]

    mocker.patch("enex2notion.cli.ensure_wkhtmltopdf")

    cli(["--mode-webclips", "PDF", "fake.enex"])

    parse_rules.mode_webclips = "PDF"

    mock_api["parse_note"].assert_called_once_with(mocker.ANY, parse_rules)


def test_webclip_pdf_with_preview(mock_api, fake_note_factory, mocker, parse_rules):
    fake_note_factory.return_value = [
        mocker.MagicMock(note_hash="fake_hash1", is_webclip=True),
    ]

    mocker.patch("enex2notion.cli.ensure_wkhtmltopdf")

    cli(["--mode-webclips", "PDF", "--add-pdf-preview", "fake.enex"])

    parse_rules.mode_webclips = "PDF"
    parse_rules.add_pdf_preview = True

    mock_api["parse_note"].assert_called_once_with(mocker.ANY, parse_rules)


def test_parse_exception(mock_api, fake_note_factory, caplog):
    fake_exception = Exception("fake")
    mock_api["parse_note"].side_effect = fake_exception

    with caplog.at_level(logging.ERROR, logger="enex2notion"):
        cli(["fake.enex"])

    assert "Failed to parse note" in caplog.text


def test_file_log(mock_api, fake_note_factory, fs):
    fs.create_file("log.txt")

    cli(["--log", "log.txt", "fake.enex"])

    with open("log.txt") as f:
        done_result = f.read()

    assert "No token provided, dry run mode." in done_result


def test_bad_token(mock_api, fake_note_factory, caplog):
    mock_api["get_notion_client"].side_effect = BadTokenException

    with caplog.at_level(logging.ERROR, logger="enex2notion"):
        with pytest.raises(SystemExit):
            cli(["--token", "fake_token", "fake.enex"])

    assert "Invalid token provided!" in caplog.text


def test_custom_tag(mock_api, fake_note_factory):
    cli(["--tag", "test_tag", "fake.enex"])

    fake_note_factory()[0].tags.append.assert_called_once_with("test_tag")


def test_cli_main_import():
    from enex2notion import __main__
