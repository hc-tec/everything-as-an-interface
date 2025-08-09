import os
import importlib
import inspect
import logging
from typing import Dict, List, Type, Any, Optional
from pathlib import Path
import importlib.util

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("plugin_manager")

class PluginManager:
    """
    插件管理器：负责插件的发现、加载、管理和生命周期控制
    """
    def __init__(self, plugin_dirs: List[str] = None):
        """
        初始化插件管理器
        
        Args:
            plugin_dirs: 插件目录列表，默认为项目内置的plugins目录
        """
        self.plugins: Dict[str, Any] = {}
        self.plugin_instances: Dict[str, Any] = {}
        self.plugin_dirs = plugin_dirs or [os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")]
        self._discover_plugins()
    
    def _discover_plugins(self) -> None:
        """发现所有可用的插件"""
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                logger.warning(f"插件目录不存在: {plugin_dir}")
                continue
                
            # 遍历目录中的所有Python文件
            for file_path in Path(plugin_dir).glob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                    
                # 生成模块路径：如果插件目录位于 src/plugins 内，则保持旧逻辑；否则使用文件路径加载
                if Path(plugin_dir).as_posix().endswith("src/plugins"):
                    module_path = f"src.plugins.{file_path.stem}"
                    try:
                        module = importlib.import_module(module_path)
                    except ModuleNotFoundError:
                        # 如果包导入失败，退回文件加载
                        module = None
                else:
                    module = None
                try:
                    if module is None:
                        # 使用文件路径加载模块
                        spec = importlib.util.spec_from_file_location(file_path.stem, str(file_path))
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)  # type: ignore
                        else:
                            raise ImportError("无法加载插件模块")
                    
                    # 查找模块中的插件类
                    for name, obj in inspect.getmembers(module):
                        # 检查是否是插件类(通过BasePlugin类型检查)
                        if (inspect.isclass(obj) and 
                            hasattr(obj, "PLUGIN_ID") and 
                            name != "BasePlugin"):
                            
                            plugin_id = obj.PLUGIN_ID
                            if plugin_id in self.plugins:
                                logger.warning(f"插件ID冲突: {plugin_id}，忽略后加载的插件")
                                continue
                                
                            self.plugins[plugin_id] = obj
                            logger.info(f"发现插件: {plugin_id} ({obj.__name__})")
                except Exception as e:
                    logger.error(f"加载插件模块失败: {module_path}, 错误: {str(e)}")
    
    def get_plugin_class(self, plugin_id: str) -> Optional[Type]:
        """获取插件类"""
        return self.plugins.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, Type]:
        """获取所有可用的插件类"""
        return self.plugins
    
    def instantiate_plugin(self, plugin_id: str, *args, **kwargs) -> Any:
        """实例化一个插件"""
        plugin_class = self.get_plugin_class(plugin_id)
        if not plugin_class:
            raise ValueError(f"未找到插件: {plugin_id}")
            
        instance = plugin_class(*args, **kwargs)
        self.plugin_instances[plugin_id] = instance
        return instance
    
    def get_plugin_instance(self, plugin_id: str) -> Any:
        """获取一个已实例化的插件"""
        return self.plugin_instances.get(plugin_id)
    
    def reload_plugins(self) -> None:
        """重新加载所有插件"""
        self.plugins = {}
        self.plugin_instances = {}
        self._discover_plugins() 