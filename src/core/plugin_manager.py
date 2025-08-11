import logging
from typing import Dict, Any

from src.core.task_config import TaskConfig

from ..plugins.registry import get_factory, list_plugins

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("plugin_manager")

class PluginManager:
    """
    插件管理器：使用注册表创建和管理插件实例
    """
    def __init__(self) -> None:
        self.plugins: Dict[str, Any] = {pid: None for pid in list_plugins()}

    def get_all_plugins(self) -> Dict[str, Any]:
        return {pid: None for pid in list_plugins()}

    def instantiate_plugin(self, plugin_id: str, ctx: Any, config: TaskConfig) -> Any:
        try:
            factory = get_factory(plugin_id)
        except KeyError:
            raise ValueError(f"未找到插件: {plugin_id}") from None
        plugin = factory(ctx, config)
        return plugin 