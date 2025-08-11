# Everything As An Interface (万物皆接口)

将各种网站和应用转换为可编程接口，实现自动化和数据聚合。

## 项目概述

现代网络中，各种应用和网站虽然为用户提供了丰富的功能，但缺乏统一的编程接口，导致用户难以整合和自动化处理这些数据。"万物皆接口"项目旨在通过浏览器自动化技术，将各种网站和应用转换为标准化的接口，让用户可以:

1. **统一访问不同平台的数据**
2. **自动化监控和处理内容更新**
3. **聚合多个来源的信息**
4. **编排跨平台的自动化工作流**

## 核心功能

- **插件系统**：为各种网站和应用提供标准化接口
- **Cookie 管理**：以 Cookie 作为登录凭证，安全存储、选择与合并注入浏览器
- **任务调度**：定时执行自动化任务
- **验证码处理**：处理登录和操作过程中的验证码
- **订阅系统**：监听并推送数据变更
- **通知中心**：多渠道发送通知和警报

## 技术栈

- **Python 3.8+**：核心编程语言
- **Playwright**：用于浏览器自动化
- **MongoDB & Redis**：数据存储和缓存
- **RabbitMQ**：消息队列
- **FastAPI**：API服务(可选)

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/everything-as-an-interface.git
cd everything-as-an-interface

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 安装Playwright浏览器
playwright install
```

### 使用示例

下面是一个监听小红书收藏夹更新的简单示例：

```python
import asyncio
from src import EverythingAsInterface

async def on_new_favorite(data):
    print(f"检测到 {len(data['new_items'])} 条新收藏:")
    for item in data['new_items']:
        print(f"标题: {item['title']}")
        print(f"作者: {item['author']}")
        print(f"链接: {item['link']}")

async def main():
    # 初始化系统
    system = EverythingAsInterface()
    
    # 首次运行手动登录，系统会自动保存 Cookie；后续可通过 cookie_ids 复用
    
    # 创建主题并订阅
    topic_id = system.subscription_system.create_topic("小红书收藏夹更新")
    system.subscription_system.subscribe(topic_id, on_new_favorite)
    
    # 添加任务
    system.scheduler.add_task(
        plugin_id="xiaohongshu",
        interval=300,  # 5分钟检查一次
        config={
            # 可选：填写已保存的 cookie_ids 以跳过手动登录
            # "cookie_ids": ["your-cookie-id-1", "your-cookie-id-2"],
            "headless": False
        }
    )
    
    # 启动调度器
    await system.scheduler.start()
    
    # 保持运行
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
```

### 运行示例程序

项目提供了一个完整的示例：

```bash
# 运行小红书收藏夹监听示例
python example.py
```

> 注意：使用前请修改示例中的账号信息。

## 项目结构

```
everything-as-an-interface/
├── src/                    # 源代码
│   ├── core/               # 核心组件
│   │   ├── plugin_manager.py      # 插件管理器
│   │   ├── scheduler.py           # 任务调度器
│   │   ├── captcha_center.py      # 验证码处理中心
│   │   ├── subscription.py        # 订阅系统
│   │   ├── notification.py        # 通知中心
│   │   └── account_manager.py     # Cookie 管理器
│   ├── plugins/            # 插件模块
│   │   ├── base.py                # 插件基类
│   │   └── xiaohongshu.py         # 小红书插件示例
│   ├── utils/              # 工具类
│   │   └── browser.py             # 浏览器自动化工具
│   └── __init__.py         # 包入口
├── example.py              # 示例程序
└── README.md               # 项目说明
```

## 开发新插件

要为新网站或应用开发插件，只需继承`BasePlugin`类并实现必要的方法：

```python
from src.plugins.base import BasePlugin

class MyNewPlugin(BasePlugin):
    # 插件元信息
    PLUGIN_ID = "my_new_plugin"
    PLUGIN_NAME = "我的新插件"
    PLUGIN_DESCRIPTION = "这是一个新插件示例"
    
    async def fetch(self):
        # 实现数据获取逻辑
        return {"success": True, "data": [...]}
```

## 贡献指南

欢迎贡献新插件或改进现有功能！贡献前，请阅读以下指南：

1. Fork 项目并创建特性分支
2. 遵循项目的代码风格和文档要求
3. 为新功能添加测试
4. 确保所有测试通过
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详情见 LICENSE 文件 