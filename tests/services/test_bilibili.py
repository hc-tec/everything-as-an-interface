import pytest

from src.services.bilibili.video_details_net import VideoDetailsNetService
from src.services.xiaohongshu.parsers import extract_initial_state
from src.utils.file_util import read_file_with_project_root
from tests.test_utils.fake_mock_function import fake_sleep, mock_query_selector_click
from tests.plugins.mock_browser import page
from tests.test_utils.get_async_generator_value import get_async_generator_value


@pytest.fixture
def bilibili_service(mocker, page):
    service = VideoDetailsNetService()
    yield service
    service.detach()

# @pytest.mark.asyncio
# async def test_bilibili_parse_video_details_with_real_dom(mocker, bilibili_service, page):
#     mocker.patch("asyncio.sleep", new=fake_sleep)
#     page = await get_async_generator_value(page)
#     bilibili_service = await get_async_generator_value(bilibili_service)
#     await bilibili_service.attach(page)
#     html = read_file_with_project_root("tests/services/bilibili/html/video_details.html")
#     await page.set_content(html)
#     favorite_item = await bilibili_service._parse_items_wrapper(html,  1, {}, {})
# 
#     assert favorite_item is not None
