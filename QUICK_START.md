# 快速开始指南

## 5分钟了解项目

### 1. 项目是什么？
这是一个自动化工具，可以将各种网站（如小红书、微博等）转换为可编程接口。

### 2. 核心工作流程
```
保存 Cookie → 选择/合并 Cookie → 注入浏览器 → 定时检查数据 → 发现变化 → 发送通知
```

### 3. 关键文件速览

#### 入口文件
- `src/__init__.py` - 系统主入口，包含 `EverythingAsInterface` 类
- `example.py` - 完整使用示例

#### 核心组件
- `src/core/account_manager.py` - Cookie 管理器（保存、选择、合并、过期清理）
- `src/core/plugin_manager.py` - 管理各种平台的插件
- `src/core/scheduler.py` - 定时执行任务
- `src/plugins/xiaohongshu.py` - 小红书插件示例

#### 工具类
- `src/utils/browser.py` - 浏览器自动化工具

## 快速理解代码

### 1. 系统初始化
```python
# 创建系统实例
system = EverythingAsInterface()

# 系统包含以下组件：
# - plugin_manager: 管理插件
# - account_manager: 管理登录会话
# - scheduler: 调度任务
# - subscription_system: 订阅数据变化
# - notification_center: 发送通知
```

### 2. 保存 Cookie（首次手动登录）
首次运行时，不需要预先创建会话。运行任务后系统会打开浏览器，手动登录成功后会自动保存 Cookie。

### 3. 手动登录获取Cookie
```python
# 首次使用时，系统会打开浏览器要求手动登录
# 登录成功后，系统会自动获取并保存Cookie
# 后续使用时会自动使用保存的Cookie
```

### 4. 创建监听任务
```python
# 创建定时任务，每5分钟检查一次
task_id = system.scheduler.add_task(
    plugin_id="xiaohongshu",
    interval=300,  # 5分钟
    config={
        # 可选：使用已保存的 cookie_ids 跳过手动登录
        # "cookie_ids": ["your-cookie-id-1", "your-cookie-id-2"],
        "headless": False
    }
)
```

### 5. 监听数据变化
```python
# 当发现新收藏时，执行回调函数
async def on_new_favorite(data):
    print(f"发现新收藏: {data['new_items']}")

# 订阅数据变化
topic_id = system.subscription_system.create_topic("小红书收藏")
system.subscription_system.subscribe(topic_id, on_new_favorite)
```

## 关键概念解释

### 1. 会话管理
- 每个平台创建一个登录会话
- 初始状态：未登录，无Cookie
- 首次使用：手动登录获取Cookie
- 后续使用：自动使用保存的Cookie
- Cookie过期：重新登录获取新Cookie

### 2. 插件系统
- 每个平台（小红书、微博等）都有对应的插件
- 插件负责登录、获取数据、处理验证码等
- 插件可以动态加载和卸载

### 3. 任务调度
- 支持定时执行任务
- 自动重试失败的任务
- 发送失败通知

### 4. 订阅系统
- 监听数据变化
- 支持数据过滤
- 自动推送变化通知

## 运行示例

### 1. 安装依赖
```bash
pip install -r requirements-dev.txt
playwright install
```

### 2. 运行示例程序
```bash
python xhs_example.py
```

### 3. 运行测试
```bash
pytest tests/core/test_account_manager.py -v
```

### 4. 使用命令行工具
```bash
# 列出可用插件
python -m src list

# 列出已保存的 Cookie
python -m src cookies list

# 运行插件
python -m src run xiaohongshu --cookies <cookie_id1,cookie_id2>
```

## 开发新插件

### 1. 创建插件文件
```python
# src/plugins/my_platform.py
from src.plugins.base import BasePlugin

class MyPlatformPlugin(BasePlugin):
    PLUGIN_ID = "my_platform"
    PLUGIN_NAME = "我的平台"
    
    async def fetch(self):
        # 实现数据获取逻辑
        return {"success": True, "data": [...]}
```

### 2. 添加平台定义
```python
# 在 account_manager.py 中添加
"my_platform": {
    "name": "我的平台",
    "cookie_domains": ["myplatform.com"],
    "login_url": "https://myplatform.com/login",
    "session_validity_days": 30,
    "requires_login": True
}
```

## 常见问题

### Q: 如何获取Cookie？
A: 系统会自动处理。首次使用时打开浏览器手动登录，登录成功后系统会自动获取并保存Cookie。

### Q: Cookie过期怎么办？
A: 系统会自动检测，过期时会重新打开浏览器要求手动登录。

### Q: 如何添加新平台？
A: 1. 在 `account_manager.py` 中添加平台定义；2. 创建对应的插件文件。

### Q: 如何自定义通知？
A: 继承 `NotificationChannel` 类，实现 `send` 方法，注册到通知中心。

## 使用流程

### 1. 首次使用
1. 运行 `python example.py`
2. 打开浏览器手动登录
3. 登录成功后自动保存 Cookie
4. 开始定时检查数据

### 2. 后续使用
1. 系统使用保存的 Cookie 自动登录（通过配置 cookie_ids 或自动检测）
2. 定时检查数据变化
3. 发现变化时发送通知

### 3. Cookie过期
1. 系统检测到 Cookie 失效并清理
2. 重新打开浏览器手动登录
3. 获取新的 Cookie 后继续运行

## 下一步

1. 阅读 `CODE_READING_GUIDE.md` 了解详细架构
2. 查看 `example.py` 了解完整使用流程
3. 阅读测试代码了解各模块的预期行为
4. 尝试开发自己的插件

这个项目采用了模块化设计，每个组件都有明确的职责，便于理解和扩展。会话管理机制确保了安全性和易用性。 