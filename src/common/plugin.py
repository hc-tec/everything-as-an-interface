from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class StopDecision:
    should_stop: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

