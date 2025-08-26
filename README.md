# Everything As An Interface (万物皆接口)

将各种网站和应用转换为可编程接口，实现自动化和数据聚合。

## 项目概述
🌐 万物皆接口

让信息，像电力一样触手可及

打开成本太高？ 收藏了的好内容，总被遗忘？消息太多，不知该看哪一个？
万物皆接口，帮你接管这一切。

我们把各大网站和应用里的关键内容，自动化抽取为“二次接口”，再交给 程序/AI 来处理。
你不需要再反复打开 App、翻找信息，只需直接获取结果。

我们能为你做到：

* ⚡ 信息监控 —— 追踪你关心的博主、话题、热榜
* 📊 数据分析 —— 聚合海量内容，生成 AI 总结报告
* 🚨 智能预警 —— 一旦触发条件，立刻通知你
* 🤖 自动操作 —— 自动执行电商监控、收藏分析等繁琐任务

在这里，信息不再分散、不再低效。
你只需思考与决策，其他交给接口与 AI。

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

pip install -r requirements-dev.txt

# 安装Playwright浏览器
playwright install
```

### 启动服务端（API + Webhook）

```bash
python run.py
```

可用接口（需在 Header 传 `X-API-Key: $EAI_API_KEY`，未设置时默认开放）

- GET `/api/v1/health` | `/api/v1/ready`
- GET `/api/v1/plugins`
- GET `/api/v1/tasks`
- POST `/api/v1/tasks` 创建任务：
  ```json
  {
    "plugin_id": "xiaohongshu_brief",
    "run_mode": "recurring",
    "interval": 300,
    "config": {"cookie_ids": ["..."], "headless": false},
    "topic_id": "可选：绑定的topic"
  }
  ```
- POST `/api/v1/plugins/{plugin_id}/run` 立即执行一次，可带 `topic_id`
- 主题与订阅：
  - GET/POST `/api/v1/topics`
  - POST `/api/v1/topics/{topic_id}/subscriptions` 注册 webhook（`url`, `secret`, `headers`）
  - GET `/api/v1/subscriptions` 列表；DELETE/PATCH `/api/v1/subscriptions/{id}`
  - POST `/api/v1/subscriptions/test-delivery?topic_id=...` 测试投递
  - POST `/api/v1/topics/{topic_id}/publish` 手动触发

Webhook 事件包含 `X-EAI-Event-Id`, `X-EAI-Topic-Id`, `X-EAI-Plugin-Id`, `X-EAI-Signature`（如配置 `secret`）。

## RPC客户端（推荐）

为了简化插件调用，我们提供了RPC风格的客户端SDK，无需手动设置webhook服务器和HTTP调用。

### 安装RPC客户端依赖

```bash
pip install -r requirements-rpc.txt
```

# 从0开始了解万物皆接口系统

## 快速开始指南

### 启动服务程序

首先启动EAI服务程序，它默认绑定到 `127.0.0.1:8008`，**注意：不开启热重载模式**（热重载会导致浏览器启动失败）。

```bash
python run.py
```

启动成功后，你将看到类似以下输出：
```
INFO - EAI API server started successfully on http://127.0.0.1:8008
INFO - Available plugins: ['xiaohongshu_brief', 'xiaohongshu_details', 'xiaohongshu_search', 'yuanbao_chat']
```

### 使用RPC客户端调用插件

查看 `client_sdk/quick_start_rpc.py` 文件，它展示了如何使用RPC客户端以便捷方式调用服务程序中的插件：

```python
import asyncio
from client_sdk.rpc_client import EAIRPCClient


async def main():
  # 创建RPC客户端
  client = EAIRPCClient(
    base_url="http://127.0.0.1:8008",  # 服务程序IP+端口
    api_key="testkey",  # 与服务程序约定的API密钥
    webhook_host="127.0.0.1",  # webhook订阅服务监听地址
    webhook_port=9002,  # webhook订阅服务端口
  )

  try:
    # 启动客户端
    await client.start()
    print("✅ RPC客户端已启动")

    # 🤖 获取小红书笔记摘要数据
    print("\n🤖 获取小红书笔记更新数据...")
    notes = await client.get_notes_brief_from_xhs(
      storage_file="data/note-brief-rpc.json",
      max_items=10,
      cookie_ids=["28ba44f1-bb67-41ab-86f0-a3d049d902aa"],
      # 不需要主动声明类似于TaskConfig()的东西，它有哪些配置就直接填哪些配置
    )
    print(f"获取到 {len(notes.get('data', []))} 条笔记更新")

  except Exception as e:
    print(f"❌ 错误: {e}")

  finally:
    # 停止客户端
    await client.stop()
    print("\n✅ RPC客户端已停止")


if __name__ == "__main__":
  asyncio.run(main())
```

### 配置说明

如果你只是想使用插件而不是自己开发插件，那接下来你只需要了解调用插件应该传入的配置是什么就行。配置分为好多种：`TaskConfig`、`ServiceConfig`，还有一些插件或服务自定义配置。**客户端只需要将根据键值填入参数即可，不用手动声明类似于TaskConfig的结构**

#### TaskConfig 通用配置

`TaskConfig` 是所有插件的通用配置，包含浏览器和任务的基本设置：

```python
from src.core.task_params import TaskConfig

config = TaskConfig(
  headless=False,  # 是否无头模式运行浏览器
  cookie_ids=["28ba44f1-bb67-41ab-86f0-a3d049d902aa"],  # 使用的Cookie ID列表
  viewport={"width": 1280, "height": 800},  # 浏览器视口大小
  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # 自定义User-Agent
  extra_http_headers={"Referer": "https://www.xiaohongshu.com"},  # 额外HTTP头
  interval=300,  # 任务执行间隔（秒）
  close_page_when_task_finished=True,  # 任务完成后是否关闭页面
  extra={  # 插件特定配置
    # 其他配置项...
  }
)
```

**常用TaskConfig参数说明：**

- `headless` (bool): 是否无头模式运行浏览器，默认 `True`
- `cookie_ids` (List[str]): 使用的Cookie ID列表，从 `accounts/cookies.enc` 中读取
- `viewport` (Dict): 浏览器视口大小，格式 `{"width": 1280, "height": 800}`
- `user_agent` (str): 自定义User-Agent字符串
- `extra_http_headers` (Dict): 额外的HTTP请求头
- `interval` (int): 任务执行间隔（秒）
- `close_page_when_task_finished` (bool): 任务完成后是否关闭页面，默认 `False`

#### ServiceConfig 通用服务配置

`ServiceConfig` 用于配置服务层的通用行为，特别是数据收集相关的设置：

```python
from src.services.base_service import ServiceConfig

service_config = ServiceConfig(
    max_items=100,  # 最大采集条数
    max_seconds=600,  # 最大执行时间（秒）
    scroll_pause_ms=800,  # 滚动暂停时间（毫秒）
    auto_scroll=True,  # 是否自动滚动
    max_idle_rounds=2,  # 最大空闲轮次
    response_timeout_sec=5.0,  # 响应超时时间（秒）
    concurrency=1,  # 并发数
    scroll_mode="default",  # 滚动模式：default/selector/pager
    scroll_selector=None,  # 自定义滚动选择器
    pager_selector=None,  # 自定义分页选择器
)
```

**常用ServiceConfig参数说明：**

- `max_items` (int): 最大采集条数，默认 `None`（无限制）
- `max_seconds` (int): 最大执行时间（秒），默认 `600`
- `scroll_pause_ms` (int): 每次滚动后的暂停时间（毫秒），默认 `800`
- `auto_scroll` (bool): 是否自动滚动加载更多内容，默认 `True`
- `max_idle_rounds` (int): 最大连续空闲轮次，超过此值停止采集，默认 `2`
- `response_timeout_sec` (float): 网络响应超时时间（秒），默认 `5.0`
- `concurrency` (int): 并发请求数，默认 `1`
- `scroll_mode` (str): 滚动模式，可选值：`"default"`, `"selector"`, `"pager"`
- `scroll_selector` (str): 自定义滚动元素选择器（当scroll_mode="selector"时使用）
- `pager_selector` (str): 自定义分页元素选择器（当scroll_mode="pager"时使用）

#### 小红书笔记摘要插件 (xiaohongshu_brief)

该插件专门用于获取小红书首页的笔记摘要信息：

```python
# 完整配置示例
config = TaskConfig(
    headless=False,
    cookie_ids=["28ba44f1-bb67-41ab-86f0-a3d049d902aa"],
    extra={
        # ServiceConfig相关配置
        "max_items": 50,  # 最大采集笔记数
        "max_seconds": 300,  # 最大执行时间
        "scroll_pause_ms": 800,  # 滚动间隔
        "auto_scroll": True,  # 启用自动滚动
        "max_idle_rounds": 3,  # 最大空闲轮次
        
        # PassiveSyncEngine配置（数据同步引擎）
        "storage_file": "data/note-briefs.json",  # 数据存储文件
        "deletion_policy": "soft",  # 删除策略：soft/hard
        "stop_after_consecutive_known": 5,  # 连续已知项目数阈值
        "stop_after_no_change_batches": 2,  # 无变化批次数阈值
        "stop_max_items": 30,  # 达到此数量时停止
        "fingerprint_fields": ["id", "title"],  # 用于去重的字段
        
        # 其他插件特定配置
        "video_output_dir": "videos_data",  # 视频输出目录
    }
)
```

**xiaohongshu_brief插件特定参数说明：**

- `storage_file` (str): 数据存储文件路径，默认 `"data/note-briefs.json"`
- `deletion_policy` (str): 删除策略，`"soft"`（标记删除）或 `"hard"`（物理删除）
- `stop_after_consecutive_known` (int): 连续遇到已知项目的数量阈值，默认 `5`
- `stop_after_no_change_batches` (int): 连续无变化的批次数阈值，默认 `2`
- `stop_max_items` (int): 达到此项目数量时停止采集，默认 `10`
- `fingerprint_fields` (List[str]): 用于生成项目指纹的字段，默认 `["id", "title"]`
- `video_output_dir` (str): 视频文件保存目录

#### 小红书笔记详情插件 (xiaohongshu_details)

用于获取小红书笔记的详细信息，包括评论、点赞等：

```python
config = TaskConfig(
    headless=False,
    cookie_ids=["your-cookie-id"],
    extra={
        # ServiceConfig
        "max_items": 20,
        "max_seconds": 180,
        
        # 插件特定配置
        "include_comments": True,  # 是否获取评论
        "max_comments_per_note": 50,  # 每条笔记最多获取评论数
        "include_author_info": True,  # 是否获取作者信息
        "save_media_files": True,  # 是否保存媒体文件
        "media_output_dir": "downloads/xhs_media",  # 媒体文件输出目录
        "note_ids": ["64b1234567890abcdef"],  # 指定要获取的笔记ID列表
    }
)
```

#### 小红书搜索插件 (xiaohongshu_search)

用于在小红书上搜索笔记：

```python
config = TaskConfig(
    headless=False,
    cookie_ids=["your-cookie-id"],
    extra={
        # ServiceConfig
        "max_items": 100,
        "max_seconds": 240,
        
        # 搜索特定配置
        "search_keywords": "美食探店",  # 搜索关键词列表
        "sort_by": "popularity",  # 排序方式：time/popularity/relevance
        "min_likes": 100,  # 最低点赞数过滤
    }
)
```

#### AI聊天插件 (yuanbao_chat)

用于与AI元宝进行对话：

```python
config = TaskConfig(
    headless=False,
    cookie_ids=["your-cookie-id"],
    extra={
        # AI对话配置
        "ask_question": "请介绍一下小红书平台的特点",  # 对话消息
        "conversation_id": "conv_123",  # 会话ID，用于保持上下文
    }
)
```

### 重要提示

1. **Cookie管理**: 首次使用任何插件都需要手动登录以保存Cookie。后续运行可以直接使用 `cookie_ids` 复用已保存的登录状态。`cookie_ids`可在登录后在日志输出中看到，**目前还未对cookie做管理上的优化！**

2. **数据存储**: 大部分插件都会将采集到的数据存储到本地文件中，请确保有足够的磁盘空间。

3. **频率控制**: 避免过于频繁的请求，建议设置合理的 `interval` 和 `scroll_pause_ms` 以减少对目标网站的压力。这样也可以避免被防爬虫和封帐号。

4. **错误处理**: 插件运行过程中可能会遇到网络错误、登录失效等情况，请在代码中添加适当的异常处理。**后续服务程序需要添加上对错误的处理功能**。

5. **资源清理**: 始终在 `finally` 块中调用 `client.stop()` 或 `await client.stop()` 来确保资源的正确释放。

### 故障排除

如果遇到问题，请检查：

1. **服务程序是否正常运行**: 访问 `http://127.0.0.1:8008/api/v1/health` 检查服务状态
2. **API密钥是否正确**: 确保客户端和服务端使用的 `api_key` 一致
3. **Cookie是否有效**: 检查 `accounts/cookies.enc` 文件中的Cookie是否过期
4. **端口是否被占用**: 确认8008端口和webhook端口未被其他程序使用
5. **依赖是否安装**: 运行 `pip install -r requirements-rpc.txt` 安装RPC客户端依赖

现在你已经了解了如何配置和使用不同的插件！根据你的具体需求选择合适的插件和配置参数即可开始使用万物皆接口系统。



# 如果你是开发者，想要更进一步了解系统
你需要先了解项目的整体架构如何
```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                外部接口层                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   FastAPI   │  │   RPC       │  │   Webhook   │  │   REST      │          │
│  │   Server    │  │   Client    │  │   Server    │  │   APIs      │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                核心业务层                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Orchestrator│  │   Scheduler │  │Subscription │  │Notification │          │
│  │  (协调器)    │  │  (调度器)    │  │   System    │  │  Center     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                插件系统层                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │PluginManager│  │ BasePlugin  │  │ Plugin      │  │ Plugin      │          │
│  │ (插件管理器)  │  │ (基类)      │  │ Registry    │  │ Factory      │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                服务层                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │NetCollection│  │ScrollHelper │  │NetConsume   │  │BaseService  │          │
│  │Service      │  │Service      │  │Helper       │  │(服务基类)     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                数据同步层                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │PassiveSync  │  │  Storage    │  │  Diff       │  │  Sync       │          │
│  │Engine       │  │  Engine     │  │  Result     │  │  Config     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                工具与配置层                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Config      │  │ Browser     │  │   Login     │  │  Error      │          │
│  │ Factory     │  │ Automation  │  │  Helper     │  │  Handler    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                基础设施层                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Playwright │  │    MongoDB  │  │    Redis    │  │   SQLite    │          │
│  │   (浏览器)   │  │   (数据)     │  │   (缓存)    │  │   (配置)    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────┘
```


架构分层说明
上面图是AI画的，还是不够好，我接下来再仔细帮你理清楚来【为什么要这样安排】
* 基础设施层
    * 依赖：浏览器自动化 Playwright，数据存储 MongoDB、Redis（SQLite 暂未启用）。
    * 作用：提供采集执行所需的运行时与持久化能力；Playwright 负责页面驱动与网络拦截，Mongo/Redis 为后续的会话、缓存、数据落地留好接口。
* 工具与配置层
    * 配置工厂 Config Factory：集中读取与注入 config.example.json5 中的配置，统一提供给 App/Browser/Database/Logging/Plugin，避免“配置散落在各处”。
    * 通用助手 Helper：LoginHelper、ScrollHelper 等把跨插件的能力抽象出来，防止把登录、滚动、网络拦截等通用逻辑塞进 BasePlugin，实现职责解耦与复用。
    * Helper类设计哲学：
        * 功能解耦：将通用功能从具体业务逻辑中抽离，避免BasePlugin变得臃肿
        * 职责单一：每个Helper专注一个领域的问题
        * 易于测试：独立的功能模块更容易进行单元测试
        * 可复用性：通用功能可以在不同插件间共享
* 数据同步层
    * PassiveSyncEngine：用于“被动对比 + 停止条件”的增量同步。首次落库后，后续批次与本地快照比对，自动识别“新增/更新”（当前删除为待完善方向），并在达到阈值时建议停止，避免无效抓取。
    * 使用场景：分页/滚动式列表（如收藏夹、搜索流、瀑布流）的批处理同步。
* 服务层与插件系统层
    * 为什么需要服务层？为了“可复用的领域逻辑”。例如“小红书瀑布流笔记收集”在首页、搜索页、发布页、收藏页都出现，抓取与解析逻辑具备高度共性，应沉淀到服务层统一实现。
    * 插件层职责：面向“入口与编排”。插件负责如何抵达目标页面、如何组合/配置具体服务、如何对接调度与事件，形成对外可调用的功能单元。
    * 关系：插件依赖服务层；服务层沉淀可复用“能力”，插件专注“场景编排与对外接口”。
* 核心业务层
    * 职责：AI这话有点大了啊，这些也就是一个擦屁股层，如统一错误处理、失败告警（邮件/通知）、验证码处理、限流/重试策略等。它让业务插件更“专注可复用逻辑”，把通用“擦屁股”能力前置到框架或者人身上。
* 外部接口层
    * 形式：FastAPI 服务端 + Webhook 分发。
    * 价值：把能力以 HTTP/RPC+Webhook 的方式暴露给任何语言与平台使用，而非局限在项目内部。你可以在任意支持 HTTP/Webhook 的技术栈里消费这些能力，进行自动化编排与数据聚合。
    * RPC SDK（python）设计哲学：
    ```python
    # 传统方式：复杂的手动HTTP调用
    import requests
    response = requests.post("http://localhost:8000/api/v1/tasks", json={
        "plugin_id": "xiaohongshu",
        "run_mode": "once",
        "config": {"cookie_ids": ["xxx"], "max_items": 10},
        "topic_id": "your-topic-id"
    })
    result = response.json()

    # RPC方式：像调用本地函数一样简单
    result = await client.get_notes_brief_from_xhs(
        cookie_ids=["xxx"],
        max_items=10
    )
    ```
更多深入内容，可查阅[开发者SOP](./docs/developer_sop.md)


## 贡献指南

欢迎贡献新插件或改进现有功能！贡献前，请阅读以下指南：

1. Fork 项目并创建特性分支
2. 遵循项目的代码风格和文档要求
3. 为新功能添加测试
4. 确保所有测试通过
5. 提交 Pull Request
