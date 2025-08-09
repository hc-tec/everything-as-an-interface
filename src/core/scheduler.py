import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Coroutine
from datetime import datetime
import uuid

logger = logging.getLogger("scheduler")

class Task:
    """任务类，表示一个待执行的任务"""
    
    def __init__(self, 
                 task_id: str,
                 plugin_id: str, 
                 interval: int, 
                 callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化任务
        
        Args:
            task_id: 任务ID
            plugin_id: 插件ID
            interval: 执行间隔(秒)
            callback: 数据处理回调函数
            config: 任务配置
        """
        self.task_id = task_id
        self.plugin_id = plugin_id
        self.interval = interval
        self.callback = callback
        self.config = config or {}
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.running = False
        self.error_count = 0
        self.success_count = 0
        self.last_error: Optional[Exception] = None
        self.last_data: Optional[Dict[str, Any]] = None
    
    def update_next_run(self) -> None:
        """更新下次执行时间"""
        self.last_run = datetime.now()
        self.next_run = datetime.fromtimestamp(time.time() + self.interval)
    
    def should_run(self) -> bool:
        """检查是否应该运行"""
        if not self.next_run:
            return True
        return datetime.now() >= self.next_run
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "task_id": self.task_id,
            "plugin_id": self.plugin_id,
            "interval": self.interval,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "running": self.running,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "has_error": self.last_error is not None,
            "last_error": str(self.last_error) if self.last_error else None,
            "config": self.config,
        }


class Scheduler:
    """调度器：负责管理和执行自动化任务"""
    
    def __init__(self):
        """初始化调度器"""
        self.tasks: Dict[str, Task] = {}
        self.plugin_manager = None  # 将在外部设置
        self.account_manager = None  # 将在外部设置
        self.notification_center = None  # 将在外部设置
        self.running = False
        self._task_loop: Optional[asyncio.Task] = None
    
    def set_plugin_manager(self, plugin_manager) -> None:
        """设置插件管理器"""
        self.plugin_manager = plugin_manager
    
    def set_account_manager(self, account_manager) -> None:
        """设置账号管理器"""
        self.account_manager = account_manager
    
    def set_notification_center(self, notification_center) -> None:
        """设置通知中心"""
        self.notification_center = notification_center
    
    def add_task(self, 
                plugin_id: str, 
                interval: int, 
                callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
                config: Optional[Dict[str, Any]] = None,
                task_id: Optional[str] = None) -> str:
        """
        添加任务
        
        Args:
            plugin_id: 插件ID
            interval: 执行间隔(秒)
            callback: 数据处理回调函数
            config: 任务配置
            task_id: 可选的任务ID，若不提供则自动生成
            
        Returns:
            任务ID
        """
        if not self.plugin_manager:
            raise RuntimeError("未设置插件管理器")
            
        # 检查插件是否存在
        if not self.plugin_manager.get_plugin_class(plugin_id):
            raise ValueError(f"插件不存在: {plugin_id}")
        
        # 生成任务ID
        task_id = task_id or str(uuid.uuid4())
        
        # 创建任务
        task = Task(
            task_id=task_id,
            plugin_id=plugin_id,
            interval=interval,
            callback=callback,
            config=config
        )
        
        # 添加到任务列表
        self.tasks[task_id] = task
        logger.info(f"添加任务: {task_id} (插件: {plugin_id}, 间隔: {interval}秒)")
        
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """
        移除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功移除
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"移除任务: {task_id}")
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务
        
        Returns:
            任务列表
        """
        return [task.to_dict() for task in self.tasks.values()]
    
    async def start(self) -> None:
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行")
            return
        
        if not self.plugin_manager:
            raise RuntimeError("未设置插件管理器")
            
        self.running = True
        logger.info("调度器已启动")
        
        # 创建调度循环
        self._task_loop = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self.running:
            logger.warning("调度器未在运行")
            return
            
        self.running = False
        
        if self._task_loop:
            self._task_loop.cancel()
            try:
                await self._task_loop
            except asyncio.CancelledError:
                pass
            self._task_loop = None
            
        logger.info("调度器已停止")
    
    async def _scheduler_loop(self) -> None:
        """调度循环，负责定期执行任务"""
        while self.running:
            await self._check_and_run_tasks()
            await asyncio.sleep(1)  # 每秒检查一次
    
    async def _check_and_run_tasks(self) -> None:
        """检查并执行到期任务"""
        for task_id, task in list(self.tasks.items()):
            if task.running:
                continue  # 跳过正在执行的任务
                
            if task.should_run():
                # 创建异步任务执行
                asyncio.create_task(self._execute_task(task))
    
    async def _execute_task(self, task: Task) -> None:
        """
        执行任务
        
        Args:
            task: 任务对象
        """
        if task.running:
            return
            
        task.running = True
        task.update_next_run()
        
        logger.info(f"执行任务: {task.task_id} (插件: {task.plugin_id})")
        
        try:
            # 实例化插件
            plugin = self.plugin_manager.instantiate_plugin(task.plugin_id)
            
            # 配置插件
            plugin.configure(task.config)
            
            # 如果插件需要账号且账号管理器可用，支持 cookie_ids 注入
            if plugin.needs_account() and self.account_manager:
                cookie_ids = task.config.get("cookie_ids") or []
                # 过滤无效/过期 Cookie
                valid_cookie_ids = []
                for cid in cookie_ids:
                    ok, _ = self.account_manager.check_cookie_validity(cid)
                    if ok:
                        valid_cookie_ids.append(cid)
                # 将账号管理器与有效的 cookie_ids 注入插件
                setattr(plugin, "account_manager", self.account_manager)
                # 使用 set_accounts 传递元信息（不含敏感 cookie 详情）
                accounts_meta = [self.account_manager._safe_cookie_info(self.account_manager.get_cookie_bundle(cid))
                                 for cid in valid_cookie_ids if self.account_manager.get_cookie_bundle(cid)]
                plugin.set_accounts(accounts_meta)
                # 同时把 cookie_ids 直接放入配置，供插件自行合并注入浏览器
                plugin.config["cookie_ids"] = valid_cookie_ids
            
            # 启动插件
            success = plugin.start()
            if not success:
                raise RuntimeError(f"插件启动失败: {task.plugin_id}")
            
            # 获取数据
            data = await plugin.fetch()
            
            # 停止插件
            plugin.stop()
            
            # 处理数据
            task.last_data = data
            task.success_count += 1
            
            # 如果有回调函数，则调用
            if task.callback and data:
                await task.callback(data)
                
            logger.info(f"任务执行成功: {task.task_id}")
            
        except Exception as e:
            task.error_count += 1
            task.last_error = e
            logger.error(f"任务执行失败: {task.task_id}, 错误: {str(e)}")
            
            # 如果通知中心可用，则发送通知
            if self.notification_center:
                await self.notification_center.send_notification(
                    level="error",
                    title=f"任务执行失败: {task.task_id}",
                    message=str(e),
                    data={
                        "task_id": task.task_id,
                        "plugin_id": task.plugin_id,
                        "error": str(e)
                    }
                )
                
        finally:
            task.running = False 