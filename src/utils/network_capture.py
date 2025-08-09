from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Optional, Union

try:
    # Typed imports for playwright; imported as Optional to avoid hard dependency at import time in tests
    from playwright.async_api import Request, Response
except Exception:  # pragma: no cover - during non-runtime contexts
    Request = Any  # type: ignore
    Response = Any  # type: ignore


# Type aliases for predicates and processors
MatchPredicate = Callable[[Union["Request", "Response"]], Union[bool, Awaitable[bool]]]
ProcessFunc = Callable[[Union["Request", "Response"]], Union[Any, Awaitable[Any]]]


@dataclass
class NetworkRule:
    """A rule describing how to match and process network traffic.

    Attributes:
        rule_id: Unique identifier for this rule.
        name: Human-readable name for the rule.
        kind: Whether the rule targets 'request' or 'response'.
        match: Predicate to decide whether the request/response should be processed.
        process: Optional processor invoked when match passes; may return any structured data.
                 If None, when matched, a default payload will be emitted (basic metadata).
        enabled: Whether the rule is active.
    """

    rule_id: str
    name: str
    kind: Literal["request", "response"]
    match: MatchPredicate
    process: Optional[ProcessFunc] = None
    enabled: bool = True

    async def matches(self, obj: Union["Request", "Response"]) -> bool:
        result = self.match(obj)
        if hasattr(result, "__await__"):
            return await result  # type: ignore[no-any-return]
        return bool(result)

    async def run_process(self, obj: Union["Request", "Response"]) -> Any:
        if self.process is None:
            # Default minimal payload
            if hasattr(obj, "url"):
                return {"url": getattr(obj, "url"), "kind": self.kind}
            return {"kind": self.kind}
        processed = self.process(obj)
        if hasattr(processed, "__await__"):
            return await processed  # type: ignore[no-any-return]
        return processed 