from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, Callable, Awaitable, Dict, Any, List

from src.services.base import NetService, T
from src.services.collection_common import NetStopDecider
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionState

@dataclass
class NoteCollectArgs:
    """Arguments for a standard note collection task."""

    goto_first: Optional[Callable[[], Awaitable[None]]] = None
    on_tick_start: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
    extra_config: Optional[Dict[str, Any]] = None

class NoteService(NetService, Generic[T]):
    """Interface for site note service implementations."""

    def __init__(self) -> None:
        super().__init__()
        self.state: Optional[NoteNetCollectionState[T]] = None

    @abstractmethod
    def set_stop_decider(self, decider: Optional[NetStopDecider[T]]) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def collect(self, args: NoteCollectArgs) -> List[T]:  # pragma: no cover - interface
        ...
