
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
    "message": "0",
    "ttl": 1,
    "data": {
        "count": 41,
        "list": [
            {
                "id": 737546928,
                "fid": 7375469,
                "mid": 475310928,
                "attr": 0,
                "attr_desc": "",
                "title": "默认收藏夹",
                "cover": "http://i1.hdslb.com/bfs/archive/33ecbf9147f807a43730f6413ffe771aebce29f2.jpg",
                "upper": {
                    "mid": 475310928,
                    "name": "ASP-SJT",
                    "face": "https://i0.hdslb.com/bfs/face/7bad9bb7e35516f4f997b3ea8578d3730b7e5587.jpg",
                    "jump_link": ""
                },
                "cover_type": 2,
                "intro": "",
                "ctime": 1570167288,
                "mtime": 1663001255,
                "state": 0,
                "fav_state": 0,
                "media_count": 1332,
                "view_count": 0,
                "vt": 0,
                "is_top": false,
                "recent_fav": null,
                "play_switch": 0,
                "type": 0,
                "link": "",
                "bvid": ""
            },
"""
class CollectionListNetService(NetService[CollectionItem]):
    """
    Bilibili收藏夹列表抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[CollectionItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/fav/folder/created/list.*", "response"),
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
        # 默认拿到的收藏夹数量很少，只有20个，在这里我们克隆请求，将分页数量修改为需要的数量
        response = state.last_response_view._original
        # context负责提供cookie
        cloner = await NetworkRequestCloner.from_response(response, context=self.page.context)
        cloner.set_query_param("ps", "100") # 一次性可拿到100个收藏夹项，应该没人能有这么多吧
        new_resp = await cloner.send(timeout_sec=20)
        payload = json.loads(new_resp.text)
        collection_list = payload.get("data").get("list")
        if not collection_list:
            return []
        ret = []
        for item in collection_list:
            id = str(item.get("id"))
            title = item.get("title")
            description = item.get("intro")
            link = item.get("url")
            item_count = item.get("media_count")
            is_default = item.get("attr") == 0
            creator = item.get("upper")
            created_time = item.get("ctime")
            updated_time = item.get("mtime")
            cover = item.get("cover")

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
                        user_id=creator.get("mid"),
                        username=creator.get("name"),
                        avatar=creator.get("face"),
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


