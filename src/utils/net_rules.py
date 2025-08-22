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
