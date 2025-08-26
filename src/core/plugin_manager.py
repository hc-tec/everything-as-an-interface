from src.config import get_logger
import importlib
import sys
from pathlib import Path
from typing import Dict, Optional

from src.core.task_params import TaskParams
from src.core.plugin_context import PluginContext
from src.config.plugin_config import PluginConfig
from src.plugins.base import BasePlugin
from ..plugins.registry import get_factory, list_plugins, PluginFactory

logger = get_logger(__name__)

class PluginManager:
    """
    插件管理器：使用注册表创建和管理插件实例
    
    Attributes:
        plugins: 插件实例字典，键为插件ID，值为插件实例或None
        plugin_config: 插件配置
    """
    
    def __init__(self, plugin_config: Optional[PluginConfig] = None) -> None:
        """初始化插件管理器。
        
        Args:
            plugin_config: 插件配置
        """
        self.plugin_config = plugin_config
        # Optional auto-discovery: import plugin modules to populate registry
        if self.plugin_config and self.plugin_config.auto_discover:
            self._auto_discover_plugins(self.plugin_config.plugins_dir)
        # Initialize cache of known ids after discovery
        self.plugins: Dict[str, Optional[BasePlugin]] = {pid: None for pid in list_plugins()}

    def _auto_discover_plugins(self, plugins_dir: Path) -> None:
        """Recursively import all plugin modules to register them via decorators.

        Skips internal modules like base/registry/dunder.
        """
        if not plugins_dir.exists():
            return

        sys.path.insert(0, str(plugins_dir.parent.parent))  # ensure src on path

        for py in plugins_dir.rglob("*.py"):
            name = py.stem
            if name in {"__init__", "base", "registry"}:
                continue

            # convert path to module name, e.g. src/plugins/foo/bar.py -> src.plugins.foo.bar
            rel_path = py.relative_to(plugins_dir.parent.parent)
            module_name = ".".join(rel_path.with_suffix("").parts)

            try:
                importlib.import_module(module_name)
                logger.debug("Auto-discovered plugin module imported: %s", module_name)
            except Exception as e:
                logger.warning("Failed to import plugin module %s: %s", module_name, str(e))

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

    def instantiate_plugin(self, plugin_id: str, ctx: PluginContext, config: TaskParams) -> BasePlugin:
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
        # 检查插件是否启用
        if self.plugin_config and not self.plugin_config.is_plugin_enabled(plugin_id):
            raise ValueError(f"插件 {plugin_id} 不能正常使用")
            
        factory = self.get_plugin_factory(plugin_id)
        plugin = factory(ctx, config)
        
        # 如果插件支持插件配置，则设置配置
        if hasattr(plugin, 'plugin_config'):
            plugin.plugin_config = self.plugin_config
            
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