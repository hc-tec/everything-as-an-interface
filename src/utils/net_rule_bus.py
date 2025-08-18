from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple, Union

from playwright.async_api import Page, Request, Response

from .net_rules import ResponseView, RequestView
from .metrics import metrics
from .global_response_listener import notify_global_listeners

NetRuleBusDelegateOnResponse = Callable[[ResponseView], Awaitable[None]]

class NetRuleBusDelegate:
    on_response: Optional[NetRuleBusDelegateOnResponse] = None


@dataclass
class Subscription:
    pattern: Pattern[str]
    kind: str  # "request" | "response"
    queue: asyncio.Queue[Union[RequestView, ResponseView]]


@dataclass
class MergedEvent:
    sub_id: int
    kind: str
    view: Union[ResponseView, RequestView]


class NetRuleBus:
    """A centralized bus for capturing network traffic and emitting events to subscribers.

    Subscribers receive pre-wrapped RequestView/ResponseView via asyncio.Queue.
    """

    def __init__(self) -> None:
        self._subs: List[Subscription] = []
        self._bound = False
        self._page: Optional[Page] = None
        self._next_id: int = 1
        self._subs_with_ids: Dict[int, Subscription] = {}
        self._delegate = NetRuleBusDelegate()
        # 跟踪每个订阅对应的转发任务，便于取消
        self._forward_tasks: Dict[int, asyncio.Task] = {}

    async def bind(self, page: Page) -> Callable[[], None]:
        if self._bound:
            return lambda: None
        self._page = page
        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._bound = True

        def unbind() -> None:
            try:
                page.off("request", self._on_request)
                page.off("response", self._on_response)
            except Exception:
                pass
            self._bound = False
        return unbind

    def subscribe(self, pattern: str, *, kind: str = "response", flags: int = 0) -> asyncio.Queue[Union[RequestView, ResponseView]]:
        """订阅网络事件模式。
        
        Args:
            pattern: 正则表达式模式
            kind: 事件类型，"request" 或 "response"
            flags: 正则表达式标志
            
        Returns:
            异步队列，用于接收匹配的网络事件
        """
        compiled = re.compile(pattern, flags)
        q: asyncio.Queue[Union[RequestView, ResponseView]] = asyncio.Queue()
        sub = Subscription(pattern=compiled, kind=kind, queue=q)
        self._subs.append(sub)
        metrics.inc("netrule.subscribe")
        return q

    def subscribe_many(self, patterns: Union[List[Tuple[str, str, int]], List[Tuple[str, str]], List[str]]) \
            -> Tuple[asyncio.Queue[MergedEvent], Dict[int, Tuple[str, str]]]:
        """订阅多个模式并返回合并队列。

        Args:
            patterns: 模式列表，支持以下格式：
                - (pattern, kind, flags)
                - (pattern, kind)  # flags 默认为 0
                - pattern (str)    # kind 默认为 "response", flags=0
                
        Returns:
            合并队列和ID到元数据的映射
        """
        merged: asyncio.Queue[MergedEvent] = asyncio.Queue()
        id_to_meta: Dict[int, Tuple[str, str]] = {}

        for p in patterns:
            if isinstance(p, str):
                pat, kind, flags = p, "response", 0
            elif isinstance(p, tuple):
                if len(p) == 2:
                    pat, kind = p
                    flags = 0
                else:
                    pat, kind, flags = p
            else:
                continue
            compiled = re.compile(pat, flags)
            sub_id = self._next_id
            self._next_id += 1
            q: asyncio.Queue[Union[RequestView, ResponseView]] = asyncio.Queue()
            sub = Subscription(pattern=compiled, kind=kind, queue=q)
            self._subs.append(sub)
            self._subs_with_ids[sub_id] = sub

            async def forward(src_q: asyncio.Queue[Union[RequestView, ResponseView]], sid: int, k: str) -> None:
                try:
                    while True:
                        item = await src_q.get()
                        await merged.put(MergedEvent(sub_id=sid, kind=k, view=item))
                        metrics.inc("netrule.forward")
                except asyncio.CancelledError:
                    # 任务被取消时正常退出
                    pass
                except Exception as e:
                    # 记录其他异常但不中断
                    metrics.inc("netrule.forward_error")

            # Background forwarders
            task = asyncio.create_task(forward(q, sub_id, kind))
            self._forward_tasks[sub_id] = task
            id_to_meta[sub_id] = (pat, kind)

        return merged, id_to_meta

    def unsubscribe_many_by_ids(self, ids: List[int]) -> None:
        """取消一组订阅并停止其转发任务。
        
        Args:
            ids: 要取消的订阅ID列表
        """
        for sid in ids:
            sub = self._subs_with_ids.pop(sid, None)
            if sub and sub in self._subs:
                try:
                    self._subs.remove(sub)
                except ValueError:
                    pass
            task = self._forward_tasks.pop(sid, None)
            if task and not task.done():
                try:
                    task.cancel()
                    metrics.inc("netrule.task_cancelled")
                except Exception:
                    pass
    
    def cleanup_all_tasks(self) -> None:
        """清理所有转发任务。
        
        在NetRuleBus实例销毁前调用，确保所有后台任务正确清理。
        """
        for task_id, task in list(self._forward_tasks.items()):
            if not task.done():
                try:
                    task.cancel()
                    metrics.inc("netrule.task_cancelled")
                except Exception:
                    pass
        self._forward_tasks.clear()
        self._subs_with_ids.clear()
        
    def get_active_subscriptions_count(self) -> int:
        """获取活跃订阅数量。
        
        Returns:
            当前活跃的订阅数量
        """
        return len(self._subs)
        
    def get_active_tasks_count(self) -> int:
        """获取活跃任务数量。
        
        Returns:
            当前活跃的转发任务数量
        """
        return len([task for task in self._forward_tasks.values() if not task.done()])

    async def _on_request(self, req: Request) -> None:
        url = getattr(req, "url", "")
        for sub in self._subs:
            if sub.kind != "request":
                continue
            if not sub.pattern.search(url):
                continue
            snap = await self._snapshot_request(req)
            await sub.queue.put(RequestView(req, snap))
            metrics.inc("netrule.request_match")

    async def _on_response(self, resp: Response) -> None:
        url = getattr(resp, "url", "")
        notified = False  # 确保全局监听只触发一次
        for sub in self._subs:
            if sub.kind != "response":
                continue
            if not sub.pattern.search(url):
                continue
            payload = await self._prefetch_response(resp)
            resp_view = ResponseView(resp, payload)
            await sub.queue.put(resp_view)
            metrics.inc("netrule.response_match")
            # 委托回调（用于本地扩展）
            if self._delegate.on_response:
                await self._delegate.on_response(resp_view)
            # 全局监听器（轻量管理器，不改变 Bus 实例化方式）
            if not notified:
                try:
                    await notify_global_listeners(resp_view)
                finally:
                    notified = True

    @staticmethod
    async def _snapshot_request(req: Request) -> Dict[str, Any]:
        snap: Dict[str, Any] = {
            "url": req.url,
            "method": getattr(req, "method", None),
            "headers": dict(req.headers) if hasattr(req, "headers") else {},
        }
        try:
            data = None
            try:
                data = await req.post_data()
            except Exception:
                data = None
            if data is None:
                try:
                    data = await req.post_data_json()
                except Exception:
                    pass
            snap["post_data"] = data
        except Exception:
            snap["post_data"] = None
        return snap

    @staticmethod
    async def _prefetch_response(resp: Response) -> Any:
        try:
            return await resp.json()
        except Exception:
            try:
                return await resp.text()
            except Exception:
                try:
                    return await resp.body()
                except Exception:
                    return None
