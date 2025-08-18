from __future__ import annotations

import asyncio
import re
import weakref
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple, Union

from playwright.async_api import Page, Request, Response

from .net_rules import ResponseView, RequestView
from .metrics import metrics
from .global_response_listener import notify_global_listeners
from .error_handler import ErrorContext, safe_execute_async

NetRuleBusDelegateOnResponse = Callable[[ResponseView], Awaitable[None]]

class NetRuleBusDelegate:
    on_response: Optional[NetRuleBusDelegateOnResponse] = None


@dataclass
class Subscription:
    pattern: Pattern[str]
    kind: str  # "request" | "response"
    queue: asyncio.Queue[Union[RequestView, ResponseView]]
    created_at: float = 0.0
    last_activity: float = 0.0
    
    def __post_init__(self) -> None:
        import time
        self.created_at = time.time()
        self.last_activity = time.time()


@dataclass
class MergedEvent:
    sub_id: int
    kind: str
    view: Union[ResponseView, RequestView]


class NetRuleBus:
    """A centralized bus for capturing network traffic and emitting events to subscribers.

    Subscribers receive pre-wrapped RequestView/ResponseView via asyncio.Queue.
    """

    def __init__(self, *, max_queue_size: int = 1000, task_timeout: float = 300.0) -> None:
        self._subs: List[Subscription] = []
        self._bound = False
        self._page: Optional[Page] = None
        self._next_id: int = 1
        self._subs_with_ids: Dict[int, Subscription] = {}
        self._delegate = NetRuleBusDelegate()
        # 跟踪每个订阅对应的转发任务，便于取消
        self._forward_tasks: Dict[int, asyncio.Task] = {}
        # 任务管理配置
        self._max_queue_size = max_queue_size
        self._task_timeout = task_timeout
        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60.0  # 每60秒清理一次
        # 弱引用集合，用于跟踪所有实例
        if not hasattr(NetRuleBus, '_instances'):
            NetRuleBus._instances = weakref.WeakSet()
        NetRuleBus._instances.add(self)

    async def bind(self, page: Page) -> Callable[[], None]:
        if self._bound:
            return lambda: None
        self._page = page
        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._bound = True
        
        # 启动自动清理任务
        await self._start_cleanup_task()

        def unbind() -> None:
            try:
                page.off("request", self._on_request)
                page.off("response", self._on_response)
            except Exception:
                pass
            # 停止清理任务
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
            self._bound = False
        return unbind

    def subscribe(self, pattern: str, *, kind: str = "response", flags: int = 0) -> asyncio.Queue[Union[RequestView, ResponseView]]:
        """订阅网络事件模式。
        
        Args:
            pattern: 正则表达式模式
            kind: 事件类型，"request" 或 "response"
            flags: 正则表达式标志
            
        Returns:
            异步队列，用于接收匹配的网络事件
        """
        compiled = re.compile(pattern, flags)
        q: asyncio.Queue[Union[RequestView, ResponseView]] = asyncio.Queue(maxsize=self._max_queue_size)
        sub = Subscription(pattern=compiled, kind=kind, queue=q)
        self._subs.append(sub)
        metrics.inc("netrule.subscribe")
        return q

    def subscribe_many(self, patterns: Union[List[Tuple[str, str, int]], List[Tuple[str, str]], List[str]]) \
            -> Tuple[asyncio.Queue[MergedEvent], Dict[int, Tuple[str, str]]]:
        """订阅多个模式并返回合并队列。

        Args:
            patterns: 模式列表，支持以下格式：
                - (pattern, kind, flags)
                - (pattern, kind)  # flags 默认为 0
                - pattern (str)    # kind 默认为 "response", flags=0
                
        Returns:
            合并队列和ID到元数据的映射
        """
        merged: asyncio.Queue[MergedEvent] = asyncio.Queue()
        id_to_meta: Dict[int, Tuple[str, str]] = {}

        for p in patterns:
            if isinstance(p, str):
                pat, kind, flags = p, "response", 0
            elif isinstance(p, tuple):
                if len(p) == 2:
                    pat, kind = p
                    flags = 0
                else:
                    pat, kind, flags = p
            else:
                continue
            compiled = re.compile(pat, flags)
            sub_id = self._next_id
            self._next_id += 1
            q: asyncio.Queue[Union[RequestView, ResponseView]] = asyncio.Queue(maxsize=self._max_queue_size)
            sub = Subscription(pattern=compiled, kind=kind, queue=q)
            self._subs.append(sub)
            self._subs_with_ids[sub_id] = sub

            async def forward(src_q: asyncio.Queue[Union[RequestView, ResponseView]], sid: int, k: str) -> None:
                context = ErrorContext(operation=f"forward_task_{sid}", subscription_id=sid, kind=k)
                try:
                    while True:
                        # 添加超时机制
                        item = await asyncio.wait_for(src_q.get(), timeout=self._task_timeout)
                        await merged.put(MergedEvent(sub_id=sid, kind=k, view=item))
                        # 更新订阅活动时间
                        if sid in self._subs_with_ids:
                            import time
                            self._subs_with_ids[sid].last_activity = time.time()
                        metrics.inc("netrule.forward")
                except asyncio.CancelledError:
                    # 任务被取消时正常退出
                    metrics.inc("netrule.task_cancelled")
                    pass
                except asyncio.TimeoutError:
                    # 超时时记录并继续
                    metrics.inc("netrule.forward_timeout")
                except Exception:
                    # 记录其他异常但不中断
                    await safe_execute_async(
                        lambda: None,
                        operation=f"forward_task_error_{sid}"
                    )
                    metrics.inc("netrule.forward_error")

            # Background forwarders
            task = asyncio.create_task(forward(q, sub_id, kind))
            self._forward_tasks[sub_id] = task
            id_to_meta[sub_id] = (pat, kind)

        return merged, id_to_meta

    def unsubscribe_many_by_ids(self, ids: List[int]) -> None:
        """取消一组订阅并停止其转发任务。
        
        Args:
            ids: 要取消的订阅ID列表
        """
        for sid in ids:
            sub = self._subs_with_ids.pop(sid, None)
            if sub and sub in self._subs:
                try:
                    self._subs.remove(sub)
                except ValueError:
                    pass
            task = self._forward_tasks.pop(sid, None)
            if task and not task.done():
                try:
                    task.cancel()
                    metrics.inc("netrule.task_cancelled")
                except Exception:
                    pass
    
    def cleanup_all_tasks(self) -> None:
        """清理所有转发任务。
        
        在NetRuleBus实例销毁前调用，确保所有后台任务正确清理。
        """
        for task_id, task in list(self._forward_tasks.items()):
            if not task.done():
                try:
                    task.cancel()
                    metrics.inc("netrule.task_cancelled")
                except Exception:
                    pass
        self._forward_tasks.clear()
        self._subs_with_ids.clear()
        
    def get_active_subscriptions_count(self) -> int:
        """获取活跃订阅数量。
        
        Returns:
            当前活跃的订阅数量
        """
        return len(self._subs)
        
    def get_active_tasks_count(self) -> int:
        """获取活跃任务数量。
        
        Returns:
            当前活跃的转发任务数量
        """
        return len([task for task in self._forward_tasks.values() if not task.done()])
        
    async def _start_cleanup_task(self) -> None:
        """启动自动清理任务。"""
        if self._cleanup_task and not self._cleanup_task.done():
            return
            
        async def cleanup_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(self._cleanup_interval)
                    await self._cleanup_stale_subscriptions()
                    await self._cleanup_completed_tasks()
                    metrics.inc("netrule.cleanup_cycle")
                except asyncio.CancelledError:
                    break
                except Exception:
                    metrics.inc("netrule.cleanup_error")
                    
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        
    async def _cleanup_stale_subscriptions(self) -> None:
        """清理过期的订阅。"""
        import time
        current_time = time.time()
        stale_threshold = 3600.0  # 1小时无活动则认为过期
        
        stale_ids = []
        for sub_id, sub in self._subs_with_ids.items():
            if current_time - sub.last_activity > stale_threshold:
                stale_ids.append(sub_id)
                
        if stale_ids:
            self.unsubscribe_many_by_ids(stale_ids)
            metrics.inc("netrule.stale_subscriptions_cleaned", len(stale_ids))
            
    async def _cleanup_completed_tasks(self) -> None:
        """清理已完成的任务。"""
        completed_ids = []
        for task_id, task in self._forward_tasks.items():
            if task.done():
                completed_ids.append(task_id)
                
        for task_id in completed_ids:
            self._forward_tasks.pop(task_id, None)
            
        if completed_ids:
            metrics.inc("netrule.completed_tasks_cleaned", len(completed_ids))
            
    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源使用统计。
        
        Returns:
            包含各种资源使用统计的字典
        """
        import time
        current_time = time.time()
        
        active_tasks = self.get_active_tasks_count()
        total_subscriptions = len(self._subs)
        
        # 计算队列使用情况
        queue_stats = []
        for sub in self._subs:
            queue_stats.append({
                'size': sub.queue.qsize(),
                'maxsize': sub.queue.maxsize,
                'age': current_time - sub.created_at,
                'last_activity': current_time - sub.last_activity
            })
            
        return {
            'active_tasks': active_tasks,
            'total_subscriptions': total_subscriptions,
            'bound': self._bound,
            'queue_stats': queue_stats,
            'cleanup_task_running': self._cleanup_task and not self._cleanup_task.done()
        }
        
    @classmethod
    def cleanup_all_instances(cls) -> None:
        """清理所有NetRuleBus实例的资源。
        
        这是一个类方法，用于在应用程序关闭时清理所有实例。
        """
        if hasattr(cls, '_instances'):
            for instance in list(cls._instances):
                try:
                    instance.cleanup_all_tasks()
                except Exception:
                    pass

    async def _on_request(self, req: Request) -> None:
        url = getattr(req, "url", "")
        context = ErrorContext(operation="handle_request", url=url)
        
        for sub in self._subs:
            if sub.kind != "request":
                continue
            if not sub.pattern.search(url):
                continue
                
            try:
                snap = await self._snapshot_request(req)
                request_view = RequestView(req, snap)
                
                # 尝试放入队列，如果队列满则跳过
                try:
                    sub.queue.put_nowait(request_view)
                    import time
                    sub.last_activity = time.time()
                    metrics.inc("netrule.request_match")
                except asyncio.QueueFull:
                    metrics.inc("netrule.queue_full")
                    # 队列满时，移除最旧的项目
                    try:
                        sub.queue.get_nowait()
                        sub.queue.put_nowait(request_view)
                        metrics.inc("netrule.queue_overflow_handled")
                    except asyncio.QueueEmpty:
                        pass
                        
            except Exception:
                await safe_execute_async(
                    lambda: None,
                    operation="request_error"
                )
                metrics.inc("netrule.request_error")

    async def _on_response(self, resp: Response) -> None:
        url = getattr(resp, "url", "")
        context = ErrorContext(operation="handle_response", url=url)
        notified = False  # 确保全局监听只触发一次
        
        for sub in self._subs:
            if sub.kind != "response":
                continue
            if not sub.pattern.search(url):
                continue
                
            try:
                payload = await self._prefetch_response(resp)
                resp_view = ResponseView(resp, payload)
                
                # 尝试放入队列，如果队列满则处理溢出
                try:
                    sub.queue.put_nowait(resp_view)
                    import time
                    sub.last_activity = time.time()
                    metrics.inc("netrule.response_match")
                except asyncio.QueueFull:
                    metrics.inc("netrule.queue_full")
                    # 队列满时，移除最旧的项目
                    try:
                        sub.queue.get_nowait()
                        sub.queue.put_nowait(resp_view)
                        metrics.inc("netrule.queue_overflow_handled")
                    except asyncio.QueueEmpty:
                        pass
                
                # 委托回调（用于本地扩展）
                if self._delegate.on_response:
                    await safe_execute_async(
                        lambda: self._delegate.on_response(resp_view),
                        operation="delegate_on_response"
                    )
                    
                # 全局监听器（轻量管理器，不改变 Bus 实例化方式）
                if not notified:
                    try:
                        await safe_execute_async(
                            lambda: notify_global_listeners(resp_view),
                            operation="notify_global_listeners"
                        )
                    finally:
                        notified = True
                        
            except Exception:
                await safe_execute_async(
                    lambda: None,
                    operation="response_error"
                )
                metrics.inc("netrule.response_error")

    @staticmethod
    async def _snapshot_request(req: Request) -> Dict[str, Any]:
        snap: Dict[str, Any] = {
            "url": req.url,
            "method": getattr(req, "method", None),
            "headers": dict(req.headers) if hasattr(req, "headers") else {},
        }
        try:
            data = None
            try:
                data = await req.post_data()
            except Exception:
                data = None
            if data is None:
                try:
                    data = await req.post_data_json()
                except Exception:
                    pass
            snap["post_data"] = data
        except Exception:
            snap["post_data"] = None
        return snap

    @staticmethod
    async def _prefetch_response(resp: Response) -> Any:
        try:
            return await resp.json()
        except Exception:
            try:
                return await resp.text()
            except Exception:
                try:
                    return await resp.body()
                except Exception:
                    return None
