import logging
from datetime import datetime

import pytest
from dateutil.tz import tzutc
from notion.block import CollectionViewPageBlock, FileBlock, PageBlock, TextBlock
from requests import HTTPError

from enex2notion.cli_notion import get_import_root
from enex2notion.enex_types import EvernoteNote
from enex2notion.enex_uploader import upload_note
from enex2notion.enex_uploader_modes import get_notebook_database, get_notebook_page
from enex2notion.note_parser.note import parse_note
from enex2notion.utils_exceptions import NoteUploadFailException


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_database(notion_test_page):
    test_database = get_notebook_database(notion_test_page, "test_database")

    properties = test_database.views[0].get("format.list_properties")

    assert isinstance(test_database, CollectionViewPageBlock)
    assert list(test_database.collection.get("schema").values()) == [
        {"name": "Tags", "type": "multi_select", "options": []},
        {"name": "URL", "type": "url"},
        {"name": "Created", "type": "created_time"},
        {"name": "Updated", "type": "last_edited_time"},
        {"name": "Title", "type": "title"},
    ]

    assert properties == test_database.collection.get(
        "format.collection_page_properties"
    )

    assert properties[0]["visible"]
    assert not properties[1]["visible"]
    assert not properties[2]["visible"]
    assert properties[3]["visible"]


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_database_existing(notion_test_page):
    test_database = get_notebook_database(notion_test_page, "test_database")

    assert test_database == get_notebook_database(notion_test_page, "test_database")


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_database_fail(notion_test_page, mocker):
    mocker.patch(
        "enex2notion.enex_uploader_modes._get_notebook_database", side_effect=Exception
    )

    with pytest.raises(NoteUploadFailException):
        get_notebook_database(notion_test_page, "test_database")


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_database_existing_no_options(notion_test_page):
    test_database = get_notebook_database(notion_test_page, "test_database")

    tag_col_id = next(
        c_k
        for c_k, c_v in test_database.collection.get("schema").items()
        if c_v["name"] == "Tags"
    )

    test_database.collection.set(f"schema.{tag_col_id}.options", None)

    test_database = get_notebook_database(notion_test_page, "test_database")

    assert test_database.collection.get(f"schema.{tag_col_id}.options") == []


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_page(notion_test_page):
    test_page = get_notebook_page(notion_test_page, "test")

    assert isinstance(test_page, PageBlock)
    assert test_page.title == "test"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_page_existing(notion_test_page):
    test_page = get_notebook_page(notion_test_page, "test")

    assert test_page == get_notebook_page(notion_test_page, "test")


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_notebook_page_fail(notion_test_page, mocker):
    mocker.patch(
        "enex2notion.enex_uploader_modes._get_notebook_page", side_effect=Exception
    )

    with pytest.raises(NoteUploadFailException):
        get_notebook_page(notion_test_page, "test")


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_import_root(notion_test_page):
    test_import_title = f"{notion_test_page.title} 2"

    root = get_import_root(notion_test_page._client, test_import_title)

    assert root == get_import_root(notion_test_page._client, test_import_title)

    root.remove(permanently=True)


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_import_root_new(notion_test_page, caplog):
    test_import_title = f"{notion_test_page.title} 2"

    root = get_import_root(notion_test_page._client, test_import_title)

    root.remove(permanently=True)

    with caplog.at_level(logging.INFO, logger="enex2notion"):
        new_root = get_import_root(notion_test_page._client, test_import_title)

    new_root.remove(permanently=True)

    assert f"Creating '{test_import_title}' page..." in caplog.text


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_empty_database_cleanup(notion_test_page):
    test_import_title = f"{notion_test_page.title} 2"

    root = get_import_root(notion_test_page._client, test_import_title)

    root.children.add_new(CollectionViewPageBlock)

    get_notebook_database(root, "test_database")

    assert len(root.children) == 1
    assert root.children[0].title == "test_database"

    root.remove(permanently=True)


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note(notion_test_page, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    note_blocks = parse_note(test_note, parse_rules)

    upload_note(notion_test_page, test_note, note_blocks, False)

    uploaded_page = notion_test_page.children[0]

    assert isinstance(uploaded_page, PageBlock)
    assert uploaded_page.title == "test1"
    assert uploaded_page.children[0].title == "test"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_with_number(notion_test_page, parse_rules):
    test_note = EvernoteNote(
        title="123. test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    note_blocks = parse_note(test_note, parse_rules)

    upload_note(notion_test_page, test_note, note_blocks, False)

    uploaded_page = notion_test_page.children[0]

    assert isinstance(uploaded_page, PageBlock)
    assert uploaded_page.title == "123. test1"
    assert uploaded_page.children[0].title == "test"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_fail(notion_test_page, mocker, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    note_blocks = parse_note(test_note, parse_rules)

    mocker.patch("enex2notion.enex_uploader.upload_block", side_effect=HTTPError)

    with pytest.raises(NoteUploadFailException):
        upload_note(notion_test_page, test_note, note_blocks, False)

    assert len(notion_test_page.children) == 0


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_fail_keep(notion_test_page, mocker, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    note_blocks = parse_note(test_note, parse_rules)

    mocker.patch("enex2notion.enex_uploader.upload_block", side_effect=HTTPError)

    with pytest.raises(NoteUploadFailException):
        upload_note(notion_test_page, test_note, note_blocks, True)

    assert len(notion_test_page.children) == 1
    assert notion_test_page.children[0].title == "test1 [UNFINISHED UPLOAD]"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_fail_db(notion_test_page, mocker, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    note_blocks = parse_note(test_note, parse_rules)

    test_database = get_notebook_database(notion_test_page, "test_database")

    mocker.patch("enex2notion.enex_uploader.upload_block", side_effect=HTTPError)

    with pytest.raises(NoteUploadFailException):
        upload_note(test_database, test_note, note_blocks, False)

    assert len(test_database.collection.get_rows()) == 0


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_with_file(notion_test_page, tiny_file, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        content=(
            "<en-note>"
            f'<en-media type="{tiny_file.mime}" hash="{tiny_file.md5}" />'
            "</en-note>"
        ),
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[tiny_file],
    )

    note_blocks = parse_note(test_note, parse_rules)

    upload_note(notion_test_page, test_note, note_blocks, False)

    uploaded_page = notion_test_page.children[0]

    assert isinstance(uploaded_page, PageBlock)
    assert uploaded_page.title == "test1"
    assert isinstance(uploaded_page.children[0], FileBlock)
    assert uploaded_page.children[0].title == "tiny.bin"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_upload_note_db(notion_test_page, parse_rules):
    test_note = EvernoteNote(
        title="test1",
        created=datetime(2021, 11, 18, 0, 0, 0, tzinfo=tzutc()),
        updated=datetime(2021, 11, 19, 0, 0, 0, tzinfo=tzutc()),
        content="<en-note><div>test</div></en-note>",
        tags=[],
        author="",
        url="",
        is_webclip=False,
        resources=[],
    )

    test_database = get_notebook_database(notion_test_page, "test_database")

    note_blocks = parse_note(test_note, parse_rules)

    upload_note(test_database, test_note, note_blocks, False)

    rows = list(test_database.collection.get_rows())
    test_row = rows[0]

    assert len(rows) == 1

    assert test_row.title == "test1"

    assert test_row.columns.created == datetime(2021, 11, 18, 0, 0, 0)
    assert test_row.columns.updated == datetime(2021, 11, 19, 0, 0, 0)
    assert test_row.columns.tags == [""]
    assert test_row.columns.url == ""

    assert len(test_row.children) == 1
    assert isinstance(test_row.children[0], TextBlock)
    assert test_row.children[0].title == "test"
