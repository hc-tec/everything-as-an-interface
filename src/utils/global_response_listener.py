"""
全局网络响应监听器管理

提供一个轻量的全局监听器注册机制，可以在任何地方注册监听函数，
然后通过现有的NetRuleBus实例来调用这些监听器。
"""

from __future__ import annotations
import asyncio
from typing import Callable, List, Awaitable
from .net_rules import ResponseView

# 全局监听器回调类型
GlobalResponseListener = Callable[[ResponseView], Awaitable[None]]

class GlobalResponseListenerManager:
    """全局响应监听器管理器"""
    
    def __init__(self) -> None:
        self._listeners: List[GlobalResponseListener] = []
    
    def add_listener(self, listener: GlobalResponseListener) -> None:
        """添加全局监听器"""
        if listener not in self._listeners:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: GlobalResponseListener) -> None:
        """移除全局监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def clear_listeners(self) -> None:
        """清空所有监听器"""
        self._listeners.clear()
    
    async def notify_all(self, response_view: ResponseView) -> None:
        """通知所有监听器"""
        if not self._listeners:
            return
        
        # 并发执行所有监听器
        tasks = [listener(response_view) for listener in self._listeners]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# 全局单例实例
_global_manager = GlobalResponseListenerManager()

def add_global_response_listener(listener: GlobalResponseListener) -> None:
    """添加全局响应监听器
    
    Args:
        listener: 异步监听函数，接收 ResponseView 参数
    """
    _global_manager.add_listener(listener)

def remove_global_response_listener(listener: GlobalResponseListener) -> None:
    """移除全局响应监听器"""
    _global_manager.remove_listener(listener)

def clear_global_response_listeners() -> None:
    """清空所有全局响应监听器"""
    _global_manager.clear_listeners()

async def notify_global_listeners(response_view: ResponseView) -> None:
    """通知所有全局监听器（内部使用）"""
    await _global_manager.notify_all(response_view)