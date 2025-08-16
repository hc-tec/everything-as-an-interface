from typing import List

import pytest

from src.services.xiaohongshu.models import NoteDetailsItem
from src.services.xiaohongshu.note_explore_page_net import XiaohongshuNoteExplorePageNetService
from src.utils.file_util import read_file_with_project_root
from tests.plugins.mock_browser import page
from tests.test_utils.get_async_generator_value import get_async_generator_value


@pytest.fixture
async def note_explore_page_net(mocker, page):
    service = XiaohongshuNoteExplorePageNetService()
    page = await get_async_generator_value(page)
    service.page = page
    yield service
    service.page = None

@pytest.mark.asyncio
async def test_parse_note_with_video(note_explore_page_net):
    # 测试视频的解析功能是否运行正常
    note_explore_page_net = await get_async_generator_value(note_explore_page_net)
    js_content = read_file_with_project_root("tests/plugins/xiaohongshu/html/note-details-url-directly-with-video.html")
    item: List[NoteDetailsItem] = await note_explore_page_net._parse_items_wrapper(js_content)
    assert item[0].video.src == "http:\u002F\u002Fsns-video-qc.xhscdn.com\u002Fstream\u002F79\u002F110\u002F114\u002F01e8940a80b2a03d4f03700198824a4fc3_114.mp4?sign=3dcb7e1a09a772137cc8873d50862feb&t=68a3eb57".replace("\u002F", "/")





