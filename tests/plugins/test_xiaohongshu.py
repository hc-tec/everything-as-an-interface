import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from playwright.async_api import ElementHandle, async_playwright

from src.plugins.xiaohongshu import XiaohongshuPlugin
from src.services.xiaohongshu.models import AuthorInfo, NoteStatistics
from tests.plugins.mock_browser import  page, mock_page, mock_context, mock_browser
from src.utils.file_util import read_file_with_project_root
from tests.test_utils.fake_mock_function import fake_sleep, mock_query_selector_click
from tests.plugins.xiaohongshu.note_card_details import NOTE_CARD_DETAILS

# @pytest.fixture
# def xhs_plugin(mocker, mock_browser):
#     xhs = XiaohongshuPlugin()
#     xhs.browser = mock_browser
#     yield xhs

# @pytest.mark.asyncio
# async def test_xhs_parse_id(mocker, xhs_plugin):
#     element = mocker.Mock(spec=ElementHandle)
#     expect_item_id = "xhs_id_1"
#     element.get_attribute = mocker.AsyncMock(return_value="xhs_id_1")
#     actual_item_id = await xhs_plugin._parse_id(element)
#     assert actual_item_id == expect_item_id

# @pytest.mark.asyncio
# async def test_load_js(xhs_plugin, page):
#     js_content = read_file_with_project_root("./extracted_initial_state.txt")
#     page = (await anext(page)) if str(type(page)) == "<class 'async_generator'>" else page
#     data = await page.evaluate(js_content)
#     note = data["note"]["noteDetailMap"]['68946e5f0000000004004a29']["note"]
#     assert note["noteId"] == '68946e5f0000000004004a29'

# @pytest.mark.asyncio
# async def test_xhs_get_span_text(xhs_plugin, page):
#     html = '''<div class="reds-tab-item sub-tab-list" style="padding:0px 16px;margin-right:0px;font-size:16px;" data-v-bb2dbd52=""><!----><!----><span>收藏</span></div>'''
#     page = (await anext(page)) if str(type(page)) == "<class 'async_generator'>" else page
#     await page.set_content(html)
#     element = await page.query_selector("span:text('收藏')")
#     text = await element.text_content()
#     assert text == "收藏"



# @pytest.mark.asyncio
# async def test_xhs_parse_id_with_real_dom(mocker, xhs_plugin, page):
#     mocker.patch("asyncio.sleep", new=fake_sleep)
#     html = read_file_with_project_root("tests/plugins/xiaohongshu/html/note-favorite-card.html")
#     page = (await anext(page)) if str(type(page)) == "<class 'async_generator'>" else page
#     await page.set_content(html)
#     element = await page.query_selector('.note-item')
#     item_id = await xhs_plugin._parse_id(element)
#     assert item_id == "6892de380000000003030e03"

# @pytest.mark.asyncio
# async def test_xhs_parse_favorite_item_with_real_dom(mocker, xhs_plugin, page):
#     mocker.patch("asyncio.sleep", new=fake_sleep)
#     page = (await anext(page)) if str(type(page)) == "<class 'async_generator'>" else page
#     mock_query_selector_click(mocker, page, [".title", ".close-circle"])
#
#     xhs_plugin.browser.context = page.context
#     xhs_plugin.browser.page = page
#     xhs_plugin.browser.browser = page.context.browser
#
#     html = read_file_with_project_root("tests/plugins/xiaohongshu/html/note-details.html")
#     await page.set_content(html)
#     favorite_item = await xhs_plugin._parse_note_from_dom(page)
#     assert favorite_item.title == "🎆"
#     assert favorite_item.author_info.username == "tama酱"
#     assert favorite_item.author_info.avatar == "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo313qhhegphk004004q3srikigbhfnvtg?imageView2/2/w/120/format/webp|imageMogr2/strip"
#     assert len(favorite_item.tags) == 1
#     assert favorite_item.tags[0] == "#甜宝小猪"
#     assert favorite_item.date == "2天前"
#     assert favorite_item.ip_zh == "江苏"
#     assert favorite_item.comment_num == " 共 116 条评论 "
#     assert favorite_item.statistic == NoteStatistics(like_num="1627", collect_num="323", chat_num="116")
#     assert favorite_item.images is None
#     assert favorite_item.video is None


# @pytest.mark.asyncio
# async def test_xhs_parse_favorite_item_with_network_data(mocker, xhs_plugin):
#     mocker.patch("asyncio.sleep", new=fake_sleep)
#
#     favorite_item = await xhs_plugin._parse_note_from_network(NOTE_CARD_DETAILS["items"])
#     assert favorite_item.title == "外人节运动大会🏆 和世界冠军一起动起来"
#     assert favorite_item.author_info.username == "户外薯"
#     assert favorite_item.author_info.avatar == "https://sns-avatar-qc.xhscdn.com/avatar/62b2d333df95c6f0a5dcd801.jpg"
#     assert len(favorite_item.tags) == 2
#     assert favorite_item.tags[0] == "小红书外人节"
#     assert favorite_item.tags[1] == "户外48小时"
#     assert favorite_item.date == 1754451991000
#     assert favorite_item.ip_zh == "新疆"
#     assert favorite_item.comment_num == "113"
#     assert favorite_item.statistic == NoteStatistics(like_num=2458, collect_num=54, chat_num=113)
#     assert len(favorite_item.images) == 11
#     assert favorite_item.video is None



