import logging
from typing import Dict, Optional

from src.core.task_config import TaskConfig
from src.core.plugin_context import PluginContext
from src.plugins.base import BasePlugin
from ..plugins.registry import get_factory, list_plugins, PluginFactory

logger = logging.getLogger("plugin_manager")

class PluginManager:
    """
    插件管理器：使用注册表创建和管理插件实例
    
    Attributes:
        plugins: 插件实例字典，键为插件ID，值为插件实例或None
    """
    
    def __init__(self) -> None:
        """初始化插件管理器。"""
        self.plugins: Dict[str, Optional[BasePlugin]] = {pid: None for pid in list_plugins()}

    def get_all_plugins(self) -> Dict[str, Optional[BasePlugin]]:
        """获取所有插件实例字典。
        
        Returns:
            插件实例字典，键为插件ID，值为插件实例或None
        """
        return {pid: None for pid in list_plugins()}
    
    def get_plugin_factory(self, plugin_id: str) -> PluginFactory:
        """获取插件工厂函数。
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件工厂函数
            
        Raises:
            ValueError: 当插件不存在时
        """
        try:
            return get_factory(plugin_id)
        except KeyError:
            raise ValueError(f"未找到插件: {plugin_id}") from None

    def instantiate_plugin(self, plugin_id: str, ctx: PluginContext, config: TaskConfig) -> BasePlugin:
        """实例化插件。
        
        Args:
            plugin_id: 插件ID
            ctx: 插件上下文
            config: 任务配置
            
        Returns:
            插件实例
            
        Raises:
            ValueError: 当插件不存在时
        """
        factory = self.get_plugin_factory(plugin_id)
        plugin = factory(ctx, config)
        self.plugins[plugin_id] = plugin
        return plugin
    
    def get_plugin_instance(self, plugin_id: str) -> Optional[BasePlugin]:
        """获取已实例化的插件。
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件实例，如果未实例化则返回None
        """
        return self.plugins.get(plugin_id)
    
    def list_available_plugins(self) -> list[str]:
        """列出所有可用的插件ID。
        
        Returns:
            插件ID列表
        """
        return list_plugins()
    
    def is_plugin_loaded(self, plugin_id: str) -> bool:
        """检查插件是否已加载。
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            True如果插件已加载，否则False
        """
        return plugin_id in self.plugins and self.plugins[plugin_id] is not None