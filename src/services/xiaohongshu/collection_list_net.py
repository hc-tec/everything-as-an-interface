
from __future__ import annotations
import asyncio
import json
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.collection_common import StopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.models import CollectionItem, AuthorInfo
from src.utils.request_clone_helper import NetworkRequestCloner

"""
{
    "code": 0,
    "success": true,
    "msg": "",
    "data": {
        "boards": [
            {
                "total": 0,
                "user": {
                    "images": "https://sns-avatar-qc.xhscdn.com/avatar/63aeb9050000000026012b9e.jpg?imageView2/2/w/80/format/jpg",
                    "red_official_verified": false,
                    "red_official_verify_type": 0,
                    "show_red_official_verify_icon": false,
                    "userid": "63aeb9050000000026012b9e",
                    "nickname": "=_="
                },
                "guest_hidden_follow_button": false,
                "desc": "暂无简介",
                "fstatus": "follows",
                "id": "68b999990000000021000d6e",
                "illegal_info": {
                    "desc": "",
                    "status": 0
                },
                "images": [],
                "name": "2",
                "privacy": 0,
                "fans": 0
            },
            {
                "fstatus": "follows",
                "id": "68b85dac00000000200344ee",
                "illegal_info": {
                    "status": 0,
                    "desc": ""
                },
                "privacy": 0,
                "total": 1,
                "user": {
                    "red_official_verified": false,
                    "red_official_verify_type": 0,
                    "show_red_official_verify_icon": false,
                    "userid": "63aeb9050000000026012b9e",
                    "nickname": "=_=",
                    "images": "https://sns-avatar-qc.xhscdn.com/avatar/63aeb9050000000026012b9e.jpg?imageView2/2/w/80/format/jpg"
                },
                "guest_hidden_follow_button": false,
                "desc": "暂无简介",
                "fans": 0,
                "images": [
                    "http://sns-na-i6.xhscdn.com/1040g2sg31lv2nj59l86g5o9si6unvu1co83eas0?imageView2/2/w/270/format/jpg/q/75"
                ],
                "name": "大撒"
            }
        ],
        "board_count": 2
    }
}
"""
class CollectionListNetService(NetService[CollectionItem]):
    """
    小红书收藏夹列表抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[CollectionItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*sns/web/v1/board/user.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def detach(self) -> None:
        self.state = None
        await self._net_helper.stop()
        self._net_helper = None
        await super().detach()

    async def invoke(self, extra_params: Dict[str, Any]) -> List[CollectionItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(extra_params)

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params,
                                                 pause_ms=pause, extra=extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            delegate=self.loop_delegate,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: NetCollectionState) -> List[CollectionItem]:

        collection_list = payload.get("data").get("boards")
        if not collection_list:
            return []
        ret = []
        for item in collection_list:
            id = str(item.get("id"))
            title = item.get("name")
            description = item.get("desc")
            link = f"https://www.xiaohongshu.com/board/{id}?source=web_user_page"
            item_count = item.get("total")
            is_default = False
            creator = item.get("user")
            created_time = None
            updated_time = None
            images = item.get("images")
            cover = images[0] if images else None

            ret.append(
                CollectionItem(
                    id=id,
                    title=title,
                    description=description,
                    cover=cover,
                    link=link,
                    item_count=item_count,
                    is_default=is_default,
                    creator=AuthorInfo(
                        user_id=creator.get("userid"),
                        username=creator.get("nickname"),
                        avatar=creator.get("images"),
                        gender=None,
                        is_following=None,
                        is_followed=None,
                        user_type=None,
                    ),
                    created_time=created_time,
                    updated_time=updated_time,
                    raw_data=self._inject_raw_data(item),
                )
            )
        return ret


