import asyncio

import pytest
import pytest_asyncio
from playwright.async_api import ElementHandle
from tests.plugins.mock_browser import page, mock_page, mock_context, mock_browser
from tests.test_utils import read_file_with_project_root
from src.plugins.xiaohongshu import XiaohongshuPlugin, AuthorInfo, NoteStatistics


@pytest.fixture
def xhs_plugin(mocker, mock_browser):
    xhs = XiaohongshuPlugin()
    xhs.browser = mock_browser
    yield xhs

# @pytest.mark.asyncio
# async def test_xhs_parse_id(mocker, xhs_plugin):
#     element = mocker.Mock(spec=ElementHandle)
#     expect_item_id = "xhs_id_1"
#     element.get_attribute = mocker.AsyncMock(return_value="xhs_id_1")
#     actual_item_id = await xhs_plugin._parse_id(element)
#     assert actual_item_id == expect_item_id

@pytest.mark.asyncio
async def test_xhs_parse_id_with_real_dom(xhs_plugin, page):
    html = read_file_with_project_root("tests/plugins/html/note-favorite-card.html")
    await page.set_content(html)
    element = await page.query_selector('.note-item')
    item_id = await xhs_plugin._parse_id(element)
    assert item_id == "6892de380000000003030e03"

@pytest.mark.asyncio
async def test_xhs_parse_favorite_item_with_real_dom(xhs_plugin, page):
    xhs_plugin.browser.context = page.context
    xhs_plugin.browser.page = page
    xhs_plugin.browser.browser = page.context.browser

    html = read_file_with_project_root("tests/plugins/html/note-details.html")
    await page.set_content(html)
    element = await page.query_selector('.note-detail-mask')
    favorite_item = await xhs_plugin._parse_favorite_item(element)
    assert favorite_item.title == "🎆"
    assert favorite_item.author_info.username == "tama酱"
    assert favorite_item.author_info.avatar == "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo313qhhegphk004004q3srikigbhfnvtg?imageView2/2/w/120/format/webp|imageMogr2/strip"
    assert len(favorite_item.tags) == 1
    assert favorite_item.tags[0] == "#甜宝小猪"
    assert favorite_item.date == "2天前"
    assert favorite_item.ip_zh == "江苏"
    assert favorite_item.comment_num == " 共 116 条评论 "
    assert favorite_item.statistic == NoteStatistics(like_num=1627, collect_num=323, chat_num=116)
    assert favorite_item.images is None
    assert favorite_item.video is None

