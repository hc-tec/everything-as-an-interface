"""
Task configuration model with common fields and an extension interface.

This module defines a dict-compatible configuration object to manage task
options. It provides strongly-typed common fields while allowing arbitrary
plugin-specific options through an extensible "extra" mapping.

Design goals:
- Keep backward compatibility with existing dict-based access patterns used
  across the codebase (e.g., config.get("headless")), by implementing a
  Mapping-like interface (get, __getitem__, __contains__, items, etc.).
- Provide typed properties for common options for clarity and auto-complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Tuple


_COMMON_KEYS: Tuple[str, ...] = (
    "headless",
    "cookie_ids",
    "viewport",
    "user_agent",
    "extra_http_headers",
    "interval",
)


@dataclass
class TaskConfig(Mapping[str, Any]):
    """Task configuration container with extensibility.

    Common options are exposed as typed attributes, while any additional
    plugin-specific options are stored in ``extra``. The object behaves like
    a read-only mapping that merges common fields and ``extra``.
    """

    # Common, strongly-typed fields
    headless: Optional[bool] = None
    cookie_ids: List[str] = field(default_factory=list)
    viewport: Optional[Dict[str, int]] = None
    user_agent: Optional[str] = None
    extra_http_headers: Optional[Dict[str, str]] = None
    # Some plugins reuse an "interval" key in their own validation;
    # keep it here for convenience although scheduler has its own interval.
    interval: Optional[int] = None

    # Extension space for plugin-specific options
    extra: Dict[str, Any] = field(default_factory=dict)

    # ----- Mapping interface -----
    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(tuple(self.keys()))

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - trivial
        yield from self.keys()

    def __getitem__(self, key: str) -> Any:
        merged = self._merged_view()
        if key not in merged:
            raise KeyError(key)
        return merged[key]

    # Provide dict-like get for backward compatibility
    def get(self, key: str, default: Any = None) -> Any:
        merged = self._merged_view()
        return merged.get(key, default)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - trivial
        if not isinstance(key, str):
            return False
        return key in self._merged_view()

    def keys(self) -> Iterable[str]:  # pragma: no cover - trivial
        seen = set()
        for k in _COMMON_KEYS:
            v = getattr(self, k if k != "cookie_ids" else "cookie_ids")
            # Treat unset None as absent for mapping semantics
            if v is not None and k not in seen:
                seen.add(k)
                yield k
        for k in self.extra.keys():
            if k not in seen:
                seen.add(k)
                yield k

    def items(self) -> Iterable[Tuple[str, Any]]:  # pragma: no cover - trivial
        for k in self.keys():
            yield k, self._merged_view()[k]

    def _merged_view(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(self.extra)
        # Only inject common keys that are explicitly set (non-None),
        # except cookie_ids which defaults to a list and should always surface.
        if self.headless is not None:
            merged["headless"] = self.headless
        merged["cookie_ids"] = list(self.cookie_ids or [])
        if self.viewport is not None:
            merged["viewport"] = self.viewport
        if self.user_agent is not None:
            merged["user_agent"] = self.user_agent
        if self.extra_http_headers is not None:
            merged["extra_http_headers"] = self.extra_http_headers
        if self.interval is not None:
            merged["interval"] = self.interval
        return merged

    # ----- Construction helpers -----
    @classmethod
    def from_dict(cls, raw: Optional[Mapping[str, Any]]) -> "TaskConfig":
        """Create a TaskConfig from an arbitrary mapping.

        Unknown keys are preserved in ``extra`` for plugin-specific use.
        """
        raw = dict(raw or {})
        common: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}

        # Extract common known keys
        for key in list(raw.keys()):
            if key in _COMMON_KEYS:
                common[key] = raw.pop(key)
        # Remaining keys are plugin-specific
        extra.update(raw)

        return cls(
            headless=cls._as_bool(common.get("headless")),
            cookie_ids=list(common.get("cookie_ids") or []),
            viewport=cls._as_dict_int(common.get("viewport")),
            user_agent=cls._as_str(common.get("user_agent")),
            extra_http_headers=cls._as_dict_str(common.get("extra_http_headers")),
            interval=cls._as_int(common.get("interval")),
            extra=extra,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict of all options (common + extra)."""
        return self._merged_view()

    # ----- Utilities & validators -----
    @staticmethod
    def _as_bool(value: Any) -> Optional[bool]:  # pragma: no cover - simple
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return bool(value)

    @staticmethod
    def _as_str(value: Any) -> Optional[str]:  # pragma: no cover - simple
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:  # pragma: no cover - simple
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _as_dict_int(value: Any) -> Optional[Dict[str, int]]:  # pragma: no cover - simple
        if not isinstance(value, dict):
            return None
        try:
            return {str(k): int(v) for k, v in value.items()}
        except Exception:
            return None

    @staticmethod
    def _as_dict_str(value: Any) -> Optional[Dict[str, str]]:  # pragma: no cover - simple
        if not isinstance(value, dict):
            return None
        try:
            return {str(k): str(v) for k, v in value.items()}
        except Exception:
            return None


