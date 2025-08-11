
from unittest.mock import AsyncMock
from typing import List

async def fake_sleep(duration):
    # 直接跳过等待
    pass

def mock_query_selector_click(
    mocker,
    page,
    selectors_to_mock: List[str]
):
    fake_ele = AsyncMock()
    fake_ele.click = AsyncMock()

    original_query_selector = page.query_selector  # 备份

    async def fake_query_selector(selector):
        if selector in selectors_to_mock:
            return fake_ele
        return await original_query_selector(selector)

    mocker.patch.object(page, "query_selector", side_effect=fake_query_selector)

    return fake_ele  # 如果你想后续校验click调用，也可以拿到这个mock对象

