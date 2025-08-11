from __future__ import annotations

import asyncio
import inspect
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Protocol, Union
from playwright.async_api import Page, Request, Response

logger = logging.getLogger("net_rules")

class SupportsDataSync(Protocol):
    def data(self) -> Any: ...


@dataclass
class RuleContext:
    pattern: Pattern[str]
    kind: str  # "request" | "response"
    match: Optional[re.Match[str]]
    func_name: str


class ResponseView:
    """A thin wrapper around Playwright Response that provides .data() synchronously.

    The dispatcher preloads JSON or text so handlers can call response.data() without await.
    """

    def __init__(self, original: Response, preloaded: Any) -> None:
        self._original = original
        self._preloaded = preloaded

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)

    def data(self) -> Any:
        return self._preloaded


class RequestView:
    """Wrapper for Playwright Request with .data() returning post_data/headers snapshot."""

    def __init__(self, original: Request, snapshot: Dict[str, Any]) -> None:
        self._original = original
        self._snapshot = snapshot

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)

    def data(self) -> Any:
        return self._snapshot


@dataclass
class _BoundRule:
    pattern: Pattern[str]
    kind: str
    handler: Callable[..., Awaitable[Any]]
    func_name: str

# 监听的请求和响应都不能更改
# 若要拦截请求数据，可用page.route
def net_rule_match(pattern: str, *, kind: str = "response", flags: int = 0) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator to mark a method as a network rule handler.

    Usage:
        @net_rule_match(r".*note_id.*", kind="response")
        async def _get_note_details(self, rule: RuleContext, response: ResponseView):
            data = response.data()
            ...
    """
    compiled = re.compile(pattern, flags)

    def _decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        setattr(func, "_net_rule", {
            "pattern": compiled,
            "kind": kind,
            "func_name": func.__name__,
        })
        return func

    return _decorator


def _collect_rules(owner: Any) -> List[_BoundRule]:
    rules: List[_BoundRule] = []
    for _, member in inspect.getmembers(owner, predicate=inspect.ismethod):
        meta = getattr(member, "_net_rule", None)
        if not meta:
            continue
        rules.append(_BoundRule(
            pattern=meta["pattern"],
            kind=meta["kind"],
            handler=member,
            func_name=meta["func_name"],
        ))
    return rules


async def _prefetch_response_payload(resp: Response) -> Any:
    try:
        return await resp.json()
    except Exception:
        try:
            return await resp.text()
        except Exception:
            try:
                body = await resp.body()
                return body
            except Exception:
                return None


async def _snapshot_request_payload(req: Request) -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "url": req.url,
        "method": getattr(req, "method", None),
        "headers": dict(req.headers) if hasattr(req, "headers") else {},
    }
    try:
        snap["post_data"] = await req.post_data  # type: ignore[attr-defined]
    except Exception:
        snap["post_data"] = None
    return snap


async def bind_network_rules(page: Page, owner: Any) -> Callable[[], None]:
    """Bind decorated network rules on a Page. Returns an unbind callable.

    This does not modify owner's DOM logic; it only wires Playwright events to the
    decorated handlers.
    """
    rules = _collect_rules(owner)
    if not rules:
        return lambda: None

    async def on_request(req: Request) -> None:
        url = getattr(req, "url", "")
        for rule in rules:
            if rule.kind != "request":
                continue
            m = rule.pattern.search(url)
            if not m:
                continue
            try:
                snap = await _snapshot_request_payload(req)
                wrapped = RequestView(req, snap)
                ctx = RuleContext(pattern=rule.pattern, kind="request", match=m, func_name=rule.func_name)
                await rule.handler(ctx, wrapped)
            except Exception as exc:  # pragma: no cover
                logger.debug(f"request rule {rule.func_name} error: {exc}")

    async def on_response(resp: Response) -> None:
        url = getattr(resp, "url", "")
        for rule in rules:
            if rule.kind != "response":
                continue
            m = rule.pattern.search(url)
            if not m:
                continue
            try:
                payload = await _prefetch_response_payload(resp)
                wrapped = ResponseView(resp, payload)
                ctx = RuleContext(pattern=rule.pattern, kind="response", match=m, func_name=rule.func_name)
                await rule.handler(ctx, wrapped)
            except Exception as exc:  # pragma: no cover
                logger.debug(f"response rule {rule.func_name} error: {exc}")

    page.on("request", on_request)
    page.on("response", on_response)

    def unbind() -> None:
        try:
            page.off("request", on_request)
            page.off("response", on_response)
        except Exception:
            pass

    return unbind