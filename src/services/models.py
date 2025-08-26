from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class WithRaw:
    raw_data: Optional[Any] # 保留原始数据（JSON、dict、甚至是未加工字符串）

