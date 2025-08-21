# Everything-as-an-Interface 开发者标准操作程序 (SOP)

## 目录

1. [项目概述](#项目概述)
2. [架构设计](#架构设计)
3. [开发环境设置](#开发环境设置)
4. [核心组件详解](#核心组件详解)
5. [插件开发指南](#插件开发指南)
6. [服务开发指南](#服务开发指南)
7. [测试规范](#测试规范)
8. [代码规范](#代码规范)
9. [部署指南](#部署指南)
10. [故障排除](#故障排除)

## 项目概述

### 项目简介

Everything-as-an-Interface 是一个基于 Python 的自动化平台，旨在将各种网站和服务转换为统一的 API 接口。该项目采用插件化架构，支持多平台数据采集、任务调度、账户管理等功能。

### 核心特性

- **插件系统**: 模块化的插件架构，支持快速扩展新平台
- **任务调度**: 基于 asyncio 的高性能任务调度器
- **账户管理**: 统一的 Cookie 和账户管理系统
- **验证码处理**: 集成验证码识别和人工干预机制
- **通知系统**: 多渠道通知支持（邮件、Webhook、控制台等）
- **订阅系统**: 实时数据订阅和推送机制
- **网络监控**: 请求/响应拦截和分析

### 技术栈

- **核心**: Python 3.8+, asyncio
- **浏览器自动化**: Playwright
- **数据存储**: MongoDB, Redis
- **消息队列**: RabbitMQ
- **Web框架**: FastAPI
- **测试**: pytest, pytest-asyncio
- **代码质量**: Ruff (格式化和检查)

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    EverythingAsInterface                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Scheduler │  │PluginManager│  │AccountManager│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │CaptchaCenter│  │Notification │  │Subscription │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                      Orchestrator                          │
│              (Browser Context Management)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Plugins   │  │   Services  │  │   Utils     │         │
│  │             │  │             │  │             │         │
│  │ - BasePlugin│  │ - BaseService│  │ - NetRules  │         │
│  │ - XHS Plugin│  │ - XHS Service│  │ - LoginHelper│        │
│  │ - ...       │  │ - ...       │  │ - ...       │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件关系

1. **EverythingAsInterface**: 系统入口，负责初始化和协调各个组件
2. **Scheduler**: 任务调度器，管理插件的执行周期
3. **PluginManager**: 插件管理器，负责插件的注册、实例化和生命周期管理
4. **Orchestrator**: 浏览器编排器，管理浏览器上下文和页面分配
5. **AccountManager**: 账户管理器，处理 Cookie 和登录状态
6. **Services**: 服务层，封装特定平台的业务逻辑

## 开发环境设置

### 环境要求

- Python 3.8+
- Node.js (用于 Playwright 浏览器下载)
- Git

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd everything-as-an-interface
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **安装 Playwright 浏览器**
   ```bash
   playwright install
   ```

5. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，配置必要的环境变量
   ```

### 开发工具配置

#### VS Code 配置

创建 `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "ruff",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

#### Ruff 配置

项目使用 Ruff 进行代码格式化和检查，配置文件为 `pyproject.toml`。

## 核心组件详解

### 1. 调度器 (Scheduler)

**位置**: `src/core/scheduler.py`

**职责**:
- 管理任务的生命周期
- 定时执行插件
- 处理任务失败和重试
- 资源分配和清理

**关键方法**:
- `add_task()`: 添加新任务
- `remove_task()`: 移除任务
- `start()`: 启动调度器
- `stop()`: 停止调度器

**使用示例**:
```python
scheduler = Scheduler()
scheduler.set_plugin_manager(plugin_manager)
scheduler.set_orchestrator(orchestrator)

# 添加任务
task_id = scheduler.add_task(
    plugin_id="xiaohongshu",
    interval=300,  # 5分钟
    config=TaskConfig.from_dict({
        "headless": True,
        "cookie_ids": ["xhs_user_1"]
    })
)

await scheduler.start()
```

### 2. 插件管理器 (PluginManager)

**位置**: `src/core/plugin_manager.py`

**职责**:
- 插件注册和发现
- 插件实例化
- 插件生命周期管理

**插件注册机制**:
```python
# 在插件文件中使用装饰器注册
@register_plugin("my_plugin")
def create_plugin(ctx: PluginContext, config: TaskConfig) -> BasePlugin:
    plugin = MyPlugin()
    plugin.configure(config)
    plugin.set_context(ctx)
    return plugin
```

### 3. 账户管理器 (AccountManager)

**位置**: `src/core/account_manager.py`

**职责**:
- Cookie 存储和加密
- 账户状态管理
- 平台配置管理

**使用示例**:
```python
account_manager = AccountManager(master_key="your_secret_key")

# 添加 Cookie
cookie_id = account_manager.add_cookies(
    platform_id="xiaohongshu",
    cookies=[
        {"name": "session", "value": "abc123", "domain": ".xiaohongshu.com"}
    ],
    name="测试账户"
)

# 获取 Cookie
cookies = account_manager.get_cookie_cookies(cookie_id)
```

### 4. 编排器 (Orchestrator)

**位置**: `src/core/orchestrator.py`

**职责**:
- 浏览器实例管理
- 上下文分配和回收
- 代理配置

**使用示例**:
```python
orchestrator = Orchestrator(
    channel="msedge",
    default_headless=True
)

await orchestrator.start()

# 分配上下文
ctx = await orchestrator.allocate_context_page(
    viewport={"width": 1920, "height": 1080},
    cookie_items=cookies
)

# 使用完毕后释放
await orchestrator.release_context_page(ctx)
```

## 插件开发指南

### 插件基础结构

所有插件必须继承 `BasePlugin` 类并实现必要的抽象方法。

**基本模板**:

```python
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig
from typing import Dict, Any
import logging

logger = logging.getLogger("plugin.my_platform")

PLUGIN_ID = "my_platform"

class MyPlatformPlugin(BasePlugin):
    """我的平台插件"""
    
    # 插件元数据
    PLUGIN_ID = PLUGIN_ID
    PLUGIN_NAME = "我的平台"
    PLUGIN_DESCRIPTION = "我的平台数据采集插件"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "开发者姓名"
    
    # 登录相关配置（可选）
    LOGIN_URL = "https://myplatform.com/login"
    PLATFORM_ID = "my_platform"
    LOGGED_IN_SELECTORS = [".user-avatar", ".logout-btn"]
    
    def __init__(self) -> None:
        super().__init__()
        # 插件特定的初始化
    
    async def start(self) -> bool:
        """启动插件"""
        logger.info(f"启动 {self.PLUGIN_NAME} 插件")
        
        # 验证配置
        if not await super().start():
            return False
        
        # 确保登录状态
        if not await self._ensure_logged_in():
            logger.error("登录失败")
            return False
        
        # 插件特定的启动逻辑
        return True
    
    async def stop(self) -> bool:
        """停止插件"""
        logger.info(f"停止 {self.PLUGIN_NAME} 插件")
        # 清理资源
        return await super().stop()
    
    async def fetch(self) -> Dict[str, Any]:
        """获取数据"""
        try:
            # 实现数据采集逻辑
            data = await self._collect_data()
            
            return {
                "success": True,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"数据采集失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _collect_data(self) -> List[Dict[str, Any]]:
        """实现具体的数据采集逻辑"""
        # 导航到目标页面
        await self.page.goto("https://myplatform.com/data")
        
        # 等待页面加载
        await self.page.wait_for_selector(".data-container")
        
        # 提取数据
        data = await self.page.evaluate("""
            () => {
                const items = document.querySelectorAll('.data-item');
                return Array.from(items).map(item => ({
                    title: item.querySelector('.title')?.textContent,
                    content: item.querySelector('.content')?.textContent,
                    url: item.querySelector('a')?.href
                }));
            }
        """)
        
        return data
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        errors = []
        
        # 检查必要的配置项
        if not self.config.get("target_url"):
            errors.append("缺少 target_url 配置")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

# 注册插件
@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, config: TaskConfig) -> MyPlatformPlugin:
    plugin = MyPlatformPlugin()
    plugin.configure(config)
    plugin.set_context(ctx)
    return plugin
```

### 插件配置

插件通过 `TaskConfig` 接收配置，支持通用配置和插件特定配置。

**通用配置**:
- `headless`: 是否无头模式
- `cookie_ids`: 使用的 Cookie ID 列表
- `viewport`: 视口大小
- `user_agent`: 用户代理
- `extra_http_headers`: 额外的 HTTP 头
- `interval`: 执行间隔（秒）

**插件特定配置**:
通过 `config.extra` 字典传递，或直接通过 `config.get("key")` 访问。

### 网络请求监控

插件可以使用网络规则来监控和拦截请求/响应。

```python
from src.utils.net_rules import NetRuleBus, ResponseView

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.net_bus = NetRuleBus()
    
    async def start(self) -> bool:
        # 注册网络监听规则
        self.net_bus.subscribe(
            "api_data",
            kind="response",
            callback=self._handle_api_response
        )
        
        # 附加到页面
        await self.net_bus.attach(self.page)
        
        return await super().start()
    
    async def _handle_api_response(self, response_view: ResponseView):
        """处理 API 响应"""
        if "/api/data" in response_view.url():
            data = response_view.json()
            # 处理响应数据
            await self._process_api_data(data)
```

## 服务开发指南

### 服务架构

服务层位于插件和具体业务逻辑之间，提供可复用的功能模块。

**基础服务类**:

```python
from src.services.base_service import BaseService
from playwright.async_api import Page
from typing import Dict, Any, Optional


class MyPlatformService(BaseService):
    """我的平台服务"""

    def __init__(self):
        super().__init__()
        self.page: Optional[Page] = None

    async def attach(self, page: Page) -> None:
        """附加到页面"""
        self.page = page
        # 设置网络监听等

    async def detach(self) -> None:
        """从页面分离"""
        # 清理资源
        self.page = None

    def configure(self, config: Dict[str, Any]) -> None:
        """配置服务"""
        self.config = config

    async def collect_data(self) -> Dict[str, Any]:
        """采集数据"""
        if not self.page:
            raise RuntimeError("服务未附加到页面")

        # 实现数据采集逻辑
        return {}
```

### 数据收集服务

对于需要分页或滚动加载的数据收集，可以使用提供的收集器基类。

```python
from src.services.paged_collector import PagedCollector
from src.services.collection_common import CollectionState

class MyDataCollector(PagedCollector):
    """我的数据收集器"""
    
    async def collect_page(self, state: CollectionState) -> List[Dict[str, Any]]:
        """收集单页数据"""
        # 实现单页数据收集逻辑
        items = await self.page.query_selector_all(".item")
        data = []
        
        for item in items:
            # 提取数据
            title = await item.query_selector(".title")
            title_text = await title.inner_text() if title else ""
            
            data.append({
                "title": title_text,
                # 其他字段
            })
        
        return data
    
    async def has_next_page(self, state: CollectionState) -> bool:
        """检查是否有下一页"""
        next_btn = await self.page.query_selector(".next-page")
        return next_btn is not None and await next_btn.is_enabled()
    
    async def go_to_next_page(self, state: CollectionState) -> bool:
        """跳转到下一页"""
        next_btn = await self.page.query_selector(".next-page")
        if next_btn:
            await next_btn.click()
            await self.page.wait_for_load_state("networkidle")
            return True
        return False
```

## 测试规范

### 测试结构

```
tests/
├── unit/                 # 单元测试
│   ├── core/            # 核心组件测试
│   ├── plugins/         # 插件测试
│   └── services/        # 服务测试
├── integration/         # 集成测试
├── e2e/                # 端到端测试
└── fixtures/           # 测试数据和夹具
```

### 测试编写规范

#### 单元测试示例

```python
import pytest
from unittest.mock import Mock, AsyncMock
from src.core.plugin_manager import PluginManager
from src.plugins.base import BasePlugin

class TestPluginManager:
    """插件管理器测试"""
    
    @pytest.fixture
    def plugin_manager(self):
        return PluginManager()
    
    @pytest.fixture
    def mock_plugin(self):
        plugin = Mock(spec=BasePlugin)
        plugin.PLUGIN_ID = "test_plugin"
        return plugin
    
    def test_get_all_plugins(self, plugin_manager):
        """测试获取所有插件"""
        plugins = plugin_manager.get_all_plugins()
        assert isinstance(plugins, dict)
    
    @pytest.mark.asyncio
    async def test_instantiate_plugin(self, plugin_manager, mock_plugin):
        """测试插件实例化"""
        # 模拟插件工厂
        def mock_factory(ctx, config):
            return mock_plugin
        
        # 注册模拟工厂
        plugin_manager._registry["test_plugin"] = mock_factory
        
        # 测试实例化
        ctx = Mock()
        config = Mock()
        plugin = plugin_manager.instantiate_plugin("test_plugin", ctx, config)
        
        assert plugin == mock_plugin
```

#### 集成测试示例

```python
import pytest
from src import EverythingAsInterface
from src.core.task_config import TaskConfig

class TestSystemIntegration:
    """系统集成测试"""
    
    @pytest.fixture
    async def system(self):
        """创建系统实例"""
        system = EverythingAsInterface()
        await system.start()
        yield system
        await system.stop()
    
    @pytest.mark.asyncio
    async def test_task_execution(self, system):
        """测试任务执行"""
        # 添加测试任务
        task_id = system.scheduler.add_task(
            plugin_id="test_plugin",
            interval=60,
            config=TaskConfig.from_dict({
                "headless": True
            })
        )
        
        assert task_id is not None
        
        # 验证任务已添加
        task = system.scheduler.get_task(task_id)
        assert task is not None
        assert task.plugin_id == "test_plugin"
```

### 测试运行

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/core/test_scheduler.py

# 运行带覆盖率的测试
pytest --cov=src --cov-report=html

# 运行特定标记的测试
pytest -m "not slow"
```

## 代码规范

### 代码风格

项目使用 Ruff 进行代码格式化和检查，遵循以下规范：

1. **导入顺序**: 标准库 → 第三方库 → 本地模块
2. **行长度**: 最大 88 字符
3. **命名规范**:
   - 类名: PascalCase
   - 函数/变量名: snake_case
   - 常量: UPPER_SNAKE_CASE
   - 私有成员: 以下划线开头

### 类型注解

所有公共 API 必须包含类型注解：

```python
from typing import Dict, List, Optional, Any

def process_data(items: List[Dict[str, Any]], 
                filter_func: Optional[Callable] = None) -> Dict[str, Any]:
    """处理数据
    
    Args:
        items: 数据项列表
        filter_func: 可选的过滤函数
    
    Returns:
        处理结果
    """
    # 实现
    pass
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def complex_function(param1: str, param2: int, param3: bool = False) -> Dict[str, Any]:
    """执行复杂操作的函数。
    
    这个函数执行一些复杂的操作，包括数据处理和验证。
    
    Args:
        param1: 第一个参数，表示操作类型
        param2: 第二个参数，表示操作次数
        param3: 可选参数，是否启用调试模式，默认为 False
    
    Returns:
        包含操作结果的字典，格式为:
        {
            "success": bool,
            "data": Any,
            "message": str
        }
    
    Raises:
        ValueError: 当 param1 为空字符串时
        RuntimeError: 当操作失败时
    
    Example:
        >>> result = complex_function("process", 5, True)
        >>> print(result["success"])
        True
    """
    pass
```

### 错误处理

使用统一的错误处理模式：

```python
import logging
from src.utils.error_handler import safe_execute_async

logger = logging.getLogger(__name__)

class MyService:
    async def risky_operation(self) -> Dict[str, Any]:
        """可能失败的操作"""
        try:
            # 执行操作
            result = await self._do_something()
            return {"success": True, "data": result}
        except SpecificException as e:
            logger.error(f"特定错误: {str(e)}")
            return {"success": False, "error": "specific_error", "message": str(e)}
        except Exception as e:
            logger.exception(f"未预期的错误: {str(e)}")
            return {"success": False, "error": "unexpected_error", "message": str(e)}
    
    async def safe_operation(self) -> Dict[str, Any]:
        """使用安全执行包装器"""
        return await safe_execute_async(
            self._do_something,
            context={"operation": "safe_operation"},
            default_return={"success": False, "data": None}
        )
```

## 部署指南

### 生产环境配置

1. **环境变量配置**
   ```bash
   # .env.production
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   DATABASE_URL=mongodb://user:pass@host:port/db
   REDIS_URL=redis://host:port/0
   RABBITMQ_URL=amqp://user:pass@host:port/
   MASTER_KEY=your_secure_master_key
   ```

2. **Docker 部署**
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   
   # 安装系统依赖
   RUN apt-get update && apt-get install -y \
       wget \
       gnupg \
       && rm -rf /var/lib/apt/lists/*
   
   # 复制依赖文件
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # 安装 Playwright 浏览器
   RUN playwright install --with-deps chromium
   
   # 复制应用代码
   COPY . .
   
   # 设置权限
   RUN chmod +x scripts/start.sh
   
   EXPOSE 8000
   
   CMD ["./scripts/start.sh"]
   ```

3. **Docker Compose**
   ```yaml
   version: '3.8'
   
   services:
     app:
       build: .
       ports:
         - "8000:8000"
       environment:
         - ENVIRONMENT=production
       depends_on:
         - mongodb
         - redis
         - rabbitmq
       volumes:
         - ./data:/app/data
         - ./logs:/app/logs
     
     mongodb:
       image: mongo:5.0
       environment:
         MONGO_INITDB_ROOT_USERNAME: admin
         MONGO_INITDB_ROOT_PASSWORD: password
       volumes:
         - mongodb_data:/data/db
     
     redis:
       image: redis:6.2-alpine
       volumes:
         - redis_data:/data
     
     rabbitmq:
       image: rabbitmq:3.9-management
       environment:
         RABBITMQ_DEFAULT_USER: admin
         RABBITMQ_DEFAULT_PASS: password
       volumes:
         - rabbitmq_data:/var/lib/rabbitmq
   
   volumes:
     mongodb_data:
     redis_data:
     rabbitmq_data:
   ```

### 监控和日志

1. **日志配置**
   ```python
   # logging_config.py
   import logging.config
   
   LOGGING_CONFIG = {
       'version': 1,
       'disable_existing_loggers': False,
       'formatters': {
           'standard': {
               'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
           },
           'detailed': {
               'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
           }
       },
       'handlers': {
           'console': {
               'class': 'logging.StreamHandler',
               'level': 'INFO',
               'formatter': 'standard'
           },
           'file': {
               'class': 'logging.handlers.RotatingFileHandler',
               'filename': 'logs/app.log',
               'maxBytes': 10485760,  # 10MB
               'backupCount': 5,
               'formatter': 'detailed'
           }
       },
       'loggers': {
           '': {
               'handlers': ['console', 'file'],
               'level': 'INFO',
               'propagate': False
           }
       }
   }
   ```

2. **健康检查**
   ```python
   # health_check.py
   from fastapi import FastAPI, HTTPException
   from src import EverythingAsInterface
   
   app = FastAPI()
   system = EverythingAsInterface()
   
   @app.get("/health")
   async def health_check():
       """健康检查端点"""
       try:
           # 检查各个组件状态
           status = {
               "scheduler": system.scheduler.is_running(),
               "plugin_manager": len(system.plugin_manager.get_all_plugins()) > 0,
               "account_manager": system.account_manager is not None,
               "timestamp": datetime.now().isoformat()
           }
           
           if all(status.values()):
               return {"status": "healthy", "details": status}
           else:
               raise HTTPException(status_code=503, detail={"status": "unhealthy", "details": status})
       except Exception as e:
           raise HTTPException(status_code=503, detail={"status": "error", "message": str(e)})
   ```

## 故障排除

### 常见问题

#### 1. 浏览器启动失败

**症状**: `Error: Browser not found` 或浏览器无法启动

**解决方案**:
```bash
# 重新安装 Playwright 浏览器
playwright install

# 安装系统依赖（Linux）
sudo apt-get install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2

# 检查浏览器路径
playwright install --dry-run
```

#### 2. Cookie 加载失败

**症状**: 登录状态丢失或 Cookie 无效

**解决方案**:
```python
# 检查 Cookie 有效性
valid, message = account_manager.check_cookie_validity(cookie_id)
if not valid:
    print(f"Cookie 无效: {message}")
    # 重新获取 Cookie

# 清理过期 Cookie
removed_count = account_manager.prune_expired_cookies()
print(f"清理了 {removed_count} 个过期 Cookie")
```

#### 3. 任务执行失败

**症状**: 任务状态显示失败或异常退出

**调试步骤**:
1. 检查日志文件
2. 验证插件配置
3. 测试网络连接
4. 检查目标网站变化

```python
# 启用详细日志
import logging
logging.getLogger().setLevel(logging.DEBUG)

# 手动执行插件进行调试
plugin = plugin_manager.instantiate_plugin("plugin_id", ctx, config)
result = await plugin.fetch()
print(result)
```

#### 4. 内存泄漏

**症状**: 长时间运行后内存使用持续增长

**解决方案**:
1. 确保正确释放浏览器上下文
2. 检查事件监听器是否正确移除
3. 使用内存分析工具

```python
# 监控内存使用
import psutil
import gc

def monitor_memory():
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")
    
    # 强制垃圾回收
    gc.collect()
```

### 调试技巧

#### 1. 启用浏览器调试

```python
# 在开发环境中启用浏览器可见模式
orchestrator = Orchestrator(
    default_headless=False,  # 显示浏览器
    channel="msedge"
)

# 启用慢动作模式
context = await browser.new_context(slow_mo=1000)  # 每个操作延迟1秒
```

#### 2. 网络请求调试

```python
# 记录所有网络请求
async def log_request(request):
    print(f"请求: {request.method} {request.url}")

async def log_response(response):
    print(f"响应: {response.status} {response.url}")

page.on("request", log_request)
page.on("response", log_response)
```

#### 3. 页面截图调试

```python
# 在关键步骤截图
await page.screenshot(path="debug_step1.png")

# 截取特定元素
element = await page.query_selector(".target-element")
if element:
    await element.screenshot(path="element.png")
```

### 性能优化

#### 1. 浏览器资源优化

```python
# 禁用不必要的资源加载
await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())

# 设置请求拦截
await page.route("**/analytics/**", lambda route: route.abort())
await page.route("**/ads/**", lambda route: route.abort())
```

#### 2. 并发控制

```python
import asyncio
from asyncio import Semaphore

class ConcurrencyManager:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = Semaphore(max_concurrent)
    
    async def execute_with_limit(self, coro):
        async with self.semaphore:
            return await coro

# 使用示例
concurrency_manager = ConcurrencyManager(max_concurrent=3)
tasks = [concurrency_manager.execute_with_limit(fetch_data(url)) for url in urls]
results = await asyncio.gather(*tasks)
```

#### 3. 缓存策略

```python
from functools import lru_cache
from typing import Dict, Any
import time

class TTLCache:
    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Any:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        self.cache[key] = (value, time.time())

# 使用缓存
cache = TTLCache(ttl=600)  # 10分钟缓存

async def get_user_info(user_id: str) -> Dict[str, Any]:
    cached = cache.get(f"user_{user_id}")
    if cached:
        return cached
    
    # 获取数据
    user_info = await fetch_user_info(user_id)
    cache.set(f"user_{user_id}", user_info)
    return user_info
```

---

## 总结

本 SOP 文档涵盖了 Everything-as-an-Interface 项目的核心开发流程和最佳实践。开发者应该：

1. **熟悉架构**: 理解系统的整体架构和各组件的职责
2. **遵循规范**: 严格按照代码规范和测试规范进行开发
3. **注重质量**: 编写高质量的代码和完善的测试
4. **持续学习**: 关注项目更新和最佳实践的演进

如有疑问或建议，请通过项目的 Issue 系统或开发者群组进行讨论。