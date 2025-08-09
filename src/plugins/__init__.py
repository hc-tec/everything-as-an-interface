"""
插件模块 - 包含各平台的自动化接口插件
"""

import os
import importlib
from typing import Dict, Any, Type

# 导入基类
from .base import BasePlugin

# 插件映射
plugins: Dict[str, Type[BasePlugin]] = {}

# 自动加载所有插件
for filename in os.listdir(os.path.dirname(__file__)):
    if filename.endswith(".py") and not filename.startswith("__"):
        module_name = filename[:-3]  # 去除 .py 后缀
        try:
            module = importlib.import_module(f"..plugins.{module_name}", __name__)
            
            # 查找模块中继承自BasePlugin的所有类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr != BasePlugin:
                    if hasattr(attr, "PLUGIN_ID") and attr.PLUGIN_ID:
                        plugins[attr.PLUGIN_ID] = attr
        except Exception as e:
            print(f"加载插件 {module_name} 失败: {str(e)}")

# 导出所有可用的插件类
__all__ = ["BasePlugin"] + list(plugins.keys()) 