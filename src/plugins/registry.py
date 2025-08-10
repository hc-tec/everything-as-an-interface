from typing import Callable, Dict, List

from .base import BasePlugin

PluginFactory = Callable[..., BasePlugin]

_REGISTRY: Dict[str, PluginFactory] = {}

def register_plugin(plugin_id: str) -> Callable[[PluginFactory], PluginFactory]:
    def _wrap(factory: PluginFactory) -> PluginFactory:
        if plugin_id in _REGISTRY:
            raise ValueError(f"插件ID已存在: {plugin_id}")
        _REGISTRY[plugin_id] = factory
        return factory
    return _wrap

def get_factory(plugin_id: str) -> PluginFactory:
    if plugin_id not in _REGISTRY:
        raise KeyError(f"未注册的插件: {plugin_id}")
    return _REGISTRY[plugin_id]

def list_plugins() -> List[str]:
    return list(_REGISTRY.keys()) 