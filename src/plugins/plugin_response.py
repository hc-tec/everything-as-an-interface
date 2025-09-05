from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union


@dataclass
class PluginResponse:
    """
    一个用于封装插件返回值的标准结构。
    """
    success: bool
    plugin_id: str
    version: str
    data: List[Any] = field(default_factory=list)
    count: int = 0
    error: Optional[str] = None

    @classmethod
    def from_success(cls, data: Union[List[Any] | Dict[str, Any]], plugin_id: str, version: str) -> "PluginResponse":
        """工厂方法：用于创建成功的响应对象。"""
        return cls(
            success=True,
            data=data,
            count=len(data) if isinstance(data, list) else None,
            plugin_id=plugin_id,
            version=version,
        )

    @classmethod
    def from_failure(cls, error_message: str, plugin_id: str, version: str) -> "PluginResponse":
        """工厂方法：用于创建失败的响应对象。"""
        return cls(
            success=False,
            error=error_message,
            plugin_id=plugin_id,
            version=version,
        )

    def to_dict(self) -> Dict[str, Any]:
        """将响应对象转换为字典，并过滤掉值为 None 的字段。"""
        # asdict 会将 dataclass 实例递归转换为字典
        result = asdict(self)
        # 过滤掉 None 值，使返回的 JSON/字典更干净
        return {k: v for k, v in result.items() if v is not None}

class ResponseFactory:
    """
    一个辅助工厂，用于创建绑定了特定插件信息的响应。
    """
    def __init__(self, plugin_id: str, version: str):
        self._plugin_id = plugin_id
        self._version = version

    def ok(self, data: Union[List[Any] | Dict[str, Any]]) -> Dict[str, Any]:
        """创建并格式化一个成功的响应字典。"""
        response = PluginResponse.from_success(
            data=data,
            plugin_id=self._plugin_id,
            version=self._version
        )
        return response.to_dict()

    def fail(self, error: str) -> Dict[str, Any]:
        """创建并格式化一个失败的响应字典。"""
        response = PluginResponse.from_failure(
            error_message=error,
            plugin_id=self._plugin_id,
            version=self._version
        )
        return response.to_dict()
