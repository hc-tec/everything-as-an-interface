from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, Callable, Awaitable, Dict, Any, List

from src.services.net_service import NetService, T
from src.services.collection_common import StopDecider
from src.services.net_collection_loop import NetCollectionState


