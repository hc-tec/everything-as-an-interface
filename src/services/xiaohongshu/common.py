from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, Callable, Awaitable, Dict, Any, List

from src.services.base_service import NetService, T
from src.services.collection_common import NetStopDecider
from src.services.net_collection import NetCollectionState

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
        self.state: Optional[NetCollectionState[T]] = None

    def set_stop_decider(self, decider: Optional[NetStopDecider[T]]) -> None:  # pragma: no cover - interface
        if self.state:
            self.state.stop_decider = decider

    @abstractmethod
    async def collect(self, args: NoteCollectArgs) -> List[T]:  # pragma: no cover - interface
        ...
