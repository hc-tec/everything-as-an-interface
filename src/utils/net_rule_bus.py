from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple

from playwright.async_api import Page, Request, Response

from .net_rules import ResponseView, RequestView


@dataclass
class Subscription:
    pattern: Pattern[str]
    kind: str  # "request" | "response"
    queue: asyncio.Queue


class NetRuleBus:
    """A centralized bus for capturing network traffic and emitting events to subscribers.

    Subscribers receive pre-wrapped RequestView/ResponseView via asyncio.Queue.
    """

    def __init__(self) -> None:
        self._subs: List[Subscription] = []
        self._bound = False
        self._page: Optional[Page] = None

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

    def subscribe(self, pattern: str, *, kind: str = "response", flags: int = 0) -> asyncio.Queue:
        compiled = re.compile(pattern, flags)
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(Subscription(pattern=compiled, kind=kind, queue=q))
        return q

    async def _on_request(self, req: Request) -> None:
        url = getattr(req, "url", "")
        for sub in self._subs:
            if sub.kind != "request":
                continue
            if not sub.pattern.search(url):
                continue
            snap = await self._snapshot_request(req)
            await sub.queue.put(RequestView(req, snap))

    async def _on_response(self, resp: Response) -> None:
        url = getattr(resp, "url", "")
        for sub in self._subs:
            if sub.kind != "response":
                continue
            if not sub.pattern.search(url):
                continue
            payload = await self._prefetch_response(resp)
            await sub.queue.put(ResponseView(resp, payload))

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