import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Callable

from src.core.scheduler import Task, Scheduler
from src.core.task_params import TaskParams
from src.utils.error_handler import ApplicationError


class TestTask:
    """Task类的测试"""
    
    def test_task_creation_basic(self):
        """测试基本任务创建"""
        task = Task(
            task_id="test_task",
            plugin_id="test_plugin",
            interval=60
        )
        
        assert task.task_id == "test_task"
        assert task.plugin_id == "test_plugin"
        assert task.interval == 60
        assert task.callback is None
        assert isinstance(task.config, TaskParams)
        assert task.last_run is None
        assert task.next_run is None
        assert task.running is False
        assert task.error_count == 0
        assert task.success_count == 0
        assert task.last_error is None
        assert task.last_data is None
    
    def test_task_creation_with_callback(self):
        """测试带回调的任务创建"""
        async def dummy_callback(data: Dict[str, Any]):
            return data
        
        config = TaskParams()
        task = Task(
            task_id="test_task",
            plugin_id="test_plugin",
            interval=60,
            callback=dummy_callback,
            config=config
        )
        
        assert task.callback == dummy_callback
        assert task.config == config
    
    def test_update_next_run(self):
        """测试更新下次运行时间"""
        task = Task("test_task", "test_plugin", 60)
        
        before_update = datetime.now()
        task.update_next_run()
        after_update = datetime.now()
        
        assert task.last_run is not None
        assert before_update <= task.last_run <= after_update
        assert task.next_run is not None
        assert task.next_run > task.last_run
    
    def test_should_run_no_next_run(self):
        """测试应该运行检查 - 没有下次运行时间"""
        task = Task("test_task", "test_plugin", 60)
        assert task.should_run() is True
    
    def test_should_run_time_reached(self):
        """测试应该运行检查 - 时间已到"""
        task = Task("test_task", "test_plugin", 60)
        task.next_run = datetime.now() - timedelta(seconds=1)
        assert task.should_run() is True
    
    def test_should_run_time_not_reached(self):
        """测试应该运行检查 - 时间未到"""
        task = Task("test_task", "test_plugin", 60)
        task.next_run = datetime.now() + timedelta(seconds=60)
        assert task.should_run() is False
    
    def test_should_run_already_running(self):
        """测试应该运行检查 - 已在运行"""
        task = Task("test_task", "test_plugin", 60)
        task.running = True
        # 根据实际实现，should_run只检查时间，不检查running状态
        # 当next_run为None时返回True
        assert task.should_run() is True
    
    def test_to_dict(self):
        """测试任务转字典"""
        task = Task("test_task", "test_plugin", 60)
        task.error_count = 2
        task.success_count = 5
        
        task_dict = task.to_dict()
        
        assert task_dict["task_id"] == "test_task"
        assert task_dict["plugin_id"] == "test_plugin"
        assert task_dict["interval"] == 60
        assert task_dict["running"] is False
        assert task_dict["error_count"] == 2
        assert task_dict["success_count"] == 5


class TestScheduler:
    """Scheduler类的测试"""
    
    @pytest.fixture
    def scheduler(self):
        """创建调度器实例"""
        return Scheduler()
    
    @pytest.fixture
    def mock_plugin_manager(self):
        """创建模拟插件管理器"""
        mock = Mock()
        mock.get_plugin_instance = Mock(return_value=Mock())
        return mock
    
    def test_scheduler_init(self, scheduler):
        """测试调度器初始化"""
        assert scheduler.tasks == {}
        assert scheduler.running is False
        assert scheduler.plugin_manager is None
        assert scheduler.account_manager is None
        assert scheduler.notification_center is None
        assert scheduler._orchestrator is None
    
    def test_set_dependencies(self, scheduler, mock_plugin_manager):
        """测试设置依赖"""
        mock_account_manager = Mock()
        mock_notification_center = Mock()
        mock_orchestrator = Mock()
        
        scheduler.set_plugin_manager(mock_plugin_manager)
        scheduler.set_account_manager(mock_account_manager)
        scheduler.set_notification_center(mock_notification_center)
        scheduler.set_orchestrator(mock_orchestrator)
        
        assert scheduler.plugin_manager == mock_plugin_manager
        assert scheduler.account_manager == mock_account_manager
        assert scheduler.notification_center == mock_notification_center
        assert scheduler._orchestrator == mock_orchestrator
    
    def test_add_task_basic(self, scheduler, mock_plugin_manager):
         """测试添加基本任务"""
         # 设置插件管理器和可用插件
         mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
         scheduler.set_plugin_manager(mock_plugin_manager)
         
         task_id = scheduler.add_task("test_plugin", 60)
         
         assert task_id in scheduler.tasks
         task = scheduler.tasks[task_id]
         assert task.plugin_id == "test_plugin"
         assert task.interval == 60
    
    def test_add_task_with_callback(self, scheduler, mock_plugin_manager):
         """测试添加带回调的任务"""
         # 设置插件管理器和可用插件
         mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
         scheduler.set_plugin_manager(mock_plugin_manager)
         
         async def dummy_callback(data: Dict[str, Any]):
             return data
         
         config = TaskParams()
         task_id = scheduler.add_task(
             "test_plugin", 
             60, 
             callback=dummy_callback,
             config=config
         )
         
         task = scheduler.tasks[task_id]
         assert task.callback == dummy_callback
         assert task.config == config
    
    def test_add_task_with_custom_id(self, scheduler, mock_plugin_manager):
         """测试添加自定义ID任务"""
         # 设置插件管理器和可用插件
         mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
         scheduler.set_plugin_manager(mock_plugin_manager)
         
         custom_id = "custom_task_id"
         task_id = scheduler.add_task(
             "test_plugin", 
             60, 
             task_id=custom_id
         )
         
         assert task_id == custom_id
         assert custom_id in scheduler.tasks
     
    def test_add_duplicate_task_id(self, scheduler, mock_plugin_manager):
        """测试添加重复任务ID"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        task_id = "duplicate_id"
        first_task_id = scheduler.add_task("test_plugin", 60, task_id=task_id)
        
        # 实际实现中会覆盖同名任务，而不是抛出异常
        second_task_id = scheduler.add_task("test_plugin", 120, task_id=task_id)
        
        assert first_task_id == second_task_id == task_id
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks[task_id].interval == 120  # 被覆盖为新的间隔
    
    def test_remove_task_success(self, scheduler, mock_plugin_manager):
        """测试成功移除任务"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        task_id = scheduler.add_task("test_plugin", 60)
        
        result = scheduler.remove_task(task_id)
        
        assert result is True
        assert task_id not in scheduler.tasks
    
    def test_remove_task_not_found(self, scheduler):
        """测试移除不存在的任务"""
        result = scheduler.remove_task("nonexistent_task")
        assert result is False
    
    def test_get_task_success(self, scheduler, mock_plugin_manager):
        """测试成功获取任务"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        task_id = scheduler.add_task("test_plugin", 60)
        
        task = scheduler.get_task(task_id)
        
        assert task is not None
        assert task.task_id == task_id
    
    def test_get_task_not_found(self, scheduler):
        """测试获取不存在的任务"""
        task = scheduler.get_task("nonexistent_task")
        assert task is None
    
    def test_get_all_tasks(self, scheduler, mock_plugin_manager):
        """测试获取所有任务"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"plugin1": {}, "plugin2": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        task_id1 = scheduler.add_task("plugin1", 60)
        task_id2 = scheduler.add_task("plugin2", 120)
        
        all_tasks = scheduler.get_all_tasks()
        
        assert len(all_tasks) == 2
        task_ids = [task["task_id"] for task in all_tasks]
        assert task_id1 in task_ids
        assert task_id2 in task_ids
    
    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler, mock_plugin_manager):
         """测试启动调度器"""
         # 设置插件管理器和orchestrator
         mock_orchestrator = Mock()
         scheduler.set_plugin_manager(mock_plugin_manager)
         scheduler.set_orchestrator(mock_orchestrator)
         
         with patch.object(scheduler, '_scheduler_loop') as mock_loop:
             mock_loop.return_value = asyncio.Future()
             mock_loop.return_value.set_result(None)
             
             await scheduler.start()
             
             assert scheduler.running is True
             mock_loop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler):
        """测试停止调度器"""
        scheduler.running = True
        
        await scheduler.stop()
        
        assert scheduler.running is False
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, scheduler, mock_plugin_manager):
         """测试成功执行任务"""
         # 设置插件管理器和可用插件
         mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
         scheduler.set_plugin_manager(mock_plugin_manager)
         
         # 设置orchestrator和account_manager
         mock_orchestrator = Mock()
         mock_account_manager = Mock()
         mock_ctx = Mock()
         
         mock_orchestrator.allocate_context_page = AsyncMock(return_value=mock_ctx)
         mock_account_manager.check_cookie_validity.return_value = (True, None)
         mock_account_manager.merge_cookies.return_value = {"test": "cookie"}
         
         scheduler.set_orchestrator(mock_orchestrator)
         scheduler.set_account_manager(mock_account_manager)
         
         # 创建模拟插件实例
         mock_plugin = Mock()
         mock_plugin.start = AsyncMock(return_value=True)
         mock_plugin.fetch = AsyncMock(return_value={"result": "success"})
         mock_plugin.stop = AsyncMock()
         mock_plugin_manager.instantiate_plugin.return_value = mock_plugin
         
         # 创建任务
         from src.core.task_params import TaskParams
         config = TaskParams(extra={"cookie_ids": ["test_cookie"]})
         task_id = scheduler.add_task("test_plugin", 60, config=config)
         task = scheduler.tasks[task_id]
         
         # 执行任务
         await scheduler._execute_task(task)
         
         # 验证结果
         assert task.success_count == 1
         assert task.error_count == 0
         assert task.last_data == {"result": "success"}
         assert task.last_error is None
    
    @pytest.mark.asyncio
    async def test_execute_task_with_callback(self, scheduler, mock_plugin_manager):
        """测试执行带回调的任务"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        # 设置orchestrator
        mock_orchestrator = Mock()
        mock_ctx = Mock()
        mock_orchestrator.allocate_context_page = AsyncMock(return_value=mock_ctx)
        scheduler.set_orchestrator(mock_orchestrator)
        
        # 创建模拟插件实例
        mock_plugin = Mock()
        mock_plugin.start = AsyncMock(return_value=True)
        mock_plugin.fetch = AsyncMock(return_value={"result": "success"})
        mock_plugin.stop = AsyncMock()
        mock_plugin_manager.instantiate_plugin.return_value = mock_plugin
        
        callback_called = False
        async def test_callback(data: Dict[str, Any]):
            nonlocal callback_called
            callback_called = True
            assert data == {"result": "success"}
        
        # 创建带回调的任务
        from src.core.task_params import TaskParams
        config = TaskParams(extra={})
        task_id = scheduler.add_task("test_plugin", 60, callback=test_callback, config=config)
        task = scheduler.tasks[task_id]
        
        # 执行任务
        await scheduler._execute_task(task)
        
        # 验证回调被调用
        assert callback_called is True
    
    @pytest.mark.asyncio
    async def test_execute_task_failure(self, scheduler, mock_plugin_manager):
        """测试任务执行失败"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        # 设置orchestrator
        mock_orchestrator = Mock()
        mock_ctx = Mock()
        mock_orchestrator.allocate_context_page = AsyncMock(return_value=mock_ctx)
        scheduler.set_orchestrator(mock_orchestrator)
        
        # 创建会抛出异常的模拟插件
        mock_plugin = Mock()
        test_error = Exception("Test error")
        mock_plugin.start = AsyncMock(return_value=True)
        mock_plugin.fetch = AsyncMock(side_effect=test_error)
        mock_plugin.stop = AsyncMock()
        mock_plugin_manager.instantiate_plugin.return_value = mock_plugin
        
        # 创建任务
        from src.core.task_params import TaskParams
        config = TaskParams(extra={})
        task_id = scheduler.add_task("test_plugin", 60, config=config)
        task = scheduler.tasks[task_id]
        
        # 执行任务
        await scheduler._execute_task(task)
        
        # 验证错误处理
        assert task.error_count == 1
        assert task.success_count == 0
        assert task.last_error == test_error
    
    @pytest.mark.asyncio
    async def test_check_and_run_tasks(self, scheduler, mock_plugin_manager):
        """测试检查和运行任务"""
        # 设置插件管理器和可用插件
        mock_plugin_manager.get_all_plugins.return_value = {"test_plugin": {}}
        scheduler.set_plugin_manager(mock_plugin_manager)
        
        # 设置orchestrator
        mock_orchestrator = Mock()
        mock_ctx = Mock()
        mock_orchestrator.allocate_context_page = AsyncMock(return_value=mock_ctx)
        scheduler.set_orchestrator(mock_orchestrator)
        
        # 创建模拟插件
        mock_plugin = Mock()
        mock_plugin.start = AsyncMock(return_value=True)
        mock_plugin.fetch = AsyncMock(return_value={"result": "success"})
        mock_plugin.stop = AsyncMock()
        mock_plugin_manager.instantiate_plugin.return_value = mock_plugin
        
        # 添加应该运行的任务
        from src.core.task_params import TaskParams
        config = TaskParams(extra={})
        task_id = scheduler.add_task("test_plugin", 60, config=config)
        task = scheduler.tasks[task_id]
        task.next_run = datetime.now() - timedelta(seconds=1)  # 设置为过去时间
        
        # 运行检查
        await scheduler._check_and_run_tasks()
        
        # 等待异步任务完成
        await asyncio.sleep(0.1)
        
        # 验证任务被执行
        assert task.success_count == 1