import random

import pytest
from notion.block import FileBlock

from enex2notion.cli_notion import get_notion_client
from enex2notion.enex_uploader_block import _extract_file_id, _sizeof_fmt, upload_block
from enex2notion.note_parser.blocks import parse_note_blocks
from enex2notion.utils_colors import COLORS_BG, COLORS_FG
from enex2notion.utils_exceptions import BadTokenException


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_color_text(parse_html, notion_test_page):
    test_colors = dict(COLORS_FG)
    test_colors.update(COLORS_BG)

    test_note = [
        f'<div><span style="color:rgb({col_rgb[0]}, {col_rgb[1]}, {col_rgb[2]});">'
        f"{col_name}</span></div>"
        for col_name, col_rgb in test_colors.items()
    ]

    test_note = parse_html("".join(test_note))
    test_blocks = parse_note_blocks(test_note)

    for block in test_blocks:
        upload_block(notion_test_page, block)

    assert len(notion_test_page.children) == len(test_blocks)
    for child, test_block in zip(notion_test_page.children, test_blocks):
        assert child.title_plaintext == test_block.attrs["title_plaintext"]
        assert (
            child.get("properties.title") == test_block.properties["properties.title"]
        )


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_embedded_link(parse_html, notion_test_page):
    test_note = parse_html(
        '<div style="--en-richlink:true;'
        " --en-href:https://google.com;"
        " --en-viewerProps:not_relevant;"
        ' --en-title:file.ext;">'
        '<a href="https://google.com" rev="en_rl_small">file.ext</a>'
        "</div>"
    )

    test_blocks = parse_note_blocks(test_note)

    for block in test_blocks:
        upload_block(notion_test_page, block)

    assert len(notion_test_page.children) == len(test_blocks)
    for child, test_block in zip(notion_test_page.children, test_blocks):
        assert child.link == test_block.attrs["link"]


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_resized_image(parse_html, notion_test_page, smallest_gif):
    test_note = parse_html(
        '<en-media type="image/gif"'
        ' style="--en-naturalWidth:100; --en-naturalHeight:200;"'
        f' hash="{smallest_gif.md5}" />'
    )

    test_blocks = parse_note_blocks(test_note)

    test_blocks[0].resource = smallest_gif
    upload_block(notion_test_page, test_blocks[0])

    assert len(notion_test_page.children) == len(test_blocks)
    for child, test_block in zip(notion_test_page.children, test_blocks):
        assert child.height == test_block.height
        assert child.width == test_block.width


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_resized_image_only_width(parse_html, notion_test_page, smallest_gif):
    test_note = parse_html(
        f'<en-media type="{smallest_gif.mime}"'
        ' style="--en-naturalWidth:100;"'
        f' hash="{smallest_gif.md5}" />'
    )

    test_blocks = parse_note_blocks(test_note)

    test_blocks[0].resource = smallest_gif
    upload_block(notion_test_page, test_blocks[0])

    assert len(notion_test_page.children) == len(test_blocks)
    for child, test_block in zip(notion_test_page.children, test_blocks):
        assert child.width == test_block.width
        assert child.height == test_block.height


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_file_upload(parse_html, notion_test_page, tiny_file):
    test_note = parse_html(
        f'<en-media type="{tiny_file.mime}" hash="{tiny_file.md5}" />'
    )

    test_blocks = parse_note_blocks(test_note)

    test_blocks[0].resource = tiny_file
    upload_block(notion_test_page, test_blocks[0])

    assert len(notion_test_page.children) == len(test_blocks)
    for child, test_block in zip(notion_test_page.children, test_blocks):
        assert isinstance(child, FileBlock)
        assert child.title == tiny_file.file_name
        assert child.size == "1B"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_table(parse_html, notion_test_page):
    test_note = parse_html(
        "<table>"
        "<tr><td>test1</td><td>test2</td><td>test3</td></tr>"
        "<tr><td>test4</td><td>test5</td><td>test6</td></tr>"
        "<tr><td>test7</td><td>test8</td><td>test9</td></tr>"
        "</table>"
    )

    random.seed(42)

    test_table = parse_note_blocks(test_note)[0]

    upload_block(notion_test_page, test_table)

    result_table = notion_test_page.children[0]
    result_order = result_table.get("format.table_block_column_order")
    result_rows = []
    for row in result_table.children:
        row_values = [row.get(f"properties.{col_id}") for col_id in result_order]

        result_rows.append(row_values)

    assert len(notion_test_page.children) == 1
    assert result_table.type == "table"
    assert len(result_table.children) == 3
    assert result_order == test_table.properties["format.table_block_column_order"]

    assert result_rows == [
        [[["test1"]], [["test2"]], [["test3"]]],
        [[["test4"]], [["test5"]], [["test6"]]],
        [[["test7"]], [["test8"]], [["test9"]]],
    ]


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_indented(parse_html, notion_test_page):
    test_note = parse_html(
        '<div>test1</div><div style="padding-left:40px;">test2</div>'
    )

    test_blocks = parse_note_blocks(test_note)

    for block in test_blocks:
        upload_block(notion_test_page, block)

    assert len(notion_test_page.children) == 1
    assert notion_test_page.children[0].title_plaintext == "test1"
    assert len(notion_test_page.children[0].children) == 1
    assert notion_test_page.children[0].children[0].title_plaintext == "test2"


@pytest.mark.vcr()
@pytest.mark.usefixtures("vcr_uuid4")
def test_bad_token():
    with pytest.raises(BadTokenException):
        get_notion_client("fake_token")


def test_upload_url_parser():
    good_url = (
        "https://prod-files-secure.s3.us-west-2.amazonaws.com/"
        "5ec22cfd-7fac-4992-a967-49fd469af9f9/"
        "5ef8c8e1-e388-4cd7-a2f3-535606b74136/test.bin"
    )

    assert _extract_file_id(good_url) == "5ef8c8e1-e388-4cd7-a2f3-535606b74136"


def test_upload_url_parser_fail():
    bad_url = "https://google.com"

    with pytest.raises(ValueError) as e:
        _extract_file_id(bad_url)

    assert e.type == ValueError
    assert str(e.value) == "Uploaded file URL format changed: https://google.com"


@pytest.mark.parametrize(
    "size,size_str",
    [
        (0, "0B"),
        (100, "100B"),
        (2000, "2.0KB"),
        (1024 * 1024 * 1024 * 1024 * 1024, "1024.0TB"),
    ],
)
def test_sizeof_fmt(size, size_str):
    assert _sizeof_fmt(size) == size_str
