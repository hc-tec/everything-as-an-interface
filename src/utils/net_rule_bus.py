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


@dataclass
class MergedEvent:
    sub_id: int
    kind: str
    view: Any  # ResponseView or RequestView


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
        sub = Subscription(pattern=compiled, kind=kind, queue=q)
        self._subs.append(sub)
        return q

    def subscribe_many(self, patterns: List[Tuple[str, str, int]] | List[Tuple[str, str]] | List[str]) -> Tuple[asyncio.Queue, Dict[int, Tuple[str, str]]]:
        """Subscribe multiple patterns and return a merged queue with (sub_id, kind, view).

        patterns elements can be:
          - (pattern, kind, flags)
          - (pattern, kind)  # flags defaults to 0
          - pattern (str)    # kind defaults to "response", flags=0
        """
        merged: asyncio.Queue = asyncio.Queue()
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
            q: asyncio.Queue = asyncio.Queue()
            sub = Subscription(pattern=compiled, kind=kind, queue=q)
            self._subs.append(sub)
            self._subs_with_ids[sub_id] = sub

            async def forward(src_q: asyncio.Queue, sid: int, k: str) -> None:
                while True:
                    item = await src_q.get()
                    await merged.put(MergedEvent(sub_id=sid, kind=k, view=item))

            # Background forwarders
            asyncio.create_task(forward(q, sub_id, kind))
            id_to_meta[sub_id] = (pat, kind)

        return merged, id_to_meta

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