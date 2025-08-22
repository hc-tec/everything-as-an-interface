from __future__ import annotations

from src.config import get_logger
from collections import defaultdict
from typing import Any, Dict, Optional

logger = get_logger(__name__)


class Metrics:
    def __init__(self) -> None:
        self.counters: Dict[str, int] = defaultdict(int)

    def inc(self, name: str, value: int = 1) -> None:
        try:
            self.counters[name] += int(value)
        except Exception:
            pass

    def get(self, name: str) -> int:
        return int(self.counters.get(name, 0))

    def event(self, name: str, **fields: Any) -> None:
        try:
            logger.debug("METRIC %s %s", name, fields)
        except Exception:
            pass


metrics = Metrics()