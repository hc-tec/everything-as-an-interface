"""
插件注册模块 - 使用显示注册机制
"""

from .base import BasePlugin
from .registry import register_plugin, get_factory, list_plugins
from .ai_web import *
from .xiaohongshu import *
