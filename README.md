# Everything As An Interface (万物皆接口)

将各种网站和应用转换为可编程接口，实现自动化和数据聚合。

## 项目概述
🌐 万物皆接口

让信息，像电力一样触手可及

网站太多，打开成本太高？ 收藏了的好内容，总被遗忘？消息太多，不知该看哪一个？
万物皆接口，帮你接管这一切。

我们把各大网站和应用里的关键内容，自动化抽取为“二次接口”，再交给 程序/AI 来处理。
你不需要再反复打开 App、翻找信息，只需直接获取结果。

在未来，我们能为你做到下面四个方面内容：

* ⚡ 信息监控 —— 追踪你关心的博主、话题、热榜
* 📊 数据分析 —— 聚合海量内容，生成 AI 总结报告
* 🚨 智能预警 —— 监听网站，一旦触发条件，立刻通知你
* 🤖 自动操作 —— 自动执行电商监控、收藏分析等繁琐任务

在这里，信息不再分散、不再低效。
你只需思考与决策，其他交给接口与 AI。

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/everything-as-an-interface.git --recursive
cd everything-as-an-interface

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

pip install -r requirements-dev.txt
pip install -r requirements-rpc.txt

# 安装Playwright浏览器
playwright install
```

# 从0开始了解万物皆接口系统

## 快速开始指南

### 启动服务程序

首先启动EAI服务程序，它默认绑定到 `127.0.0.1:8008`，**注意：默认不开启热重载模式**（热重载会导致浏览器启动失败）。

```bash
python run.py
```

启动成功后，你将看到类似以下输出：
```
--- [DEBUG] Event loop policy successfully set to ProactorEventLoopPolicy. ---
INFO:     Started server process [6300]
INFO:     Waiting for application startup.
WARNING:root:Warning: Failed to load config file D:\everything-as-an-interface2\config.example.json5 with json: Expecting property name enclosed in double quotes: line 5 column 5 (char 70)
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.ai_web.yuanbao_chat
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.xiaohongshu.xiaohongshu
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.xiaohongshu.xiaohongshu_details
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.xiaohongshu.xiaohongshu_favorites_brief
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.xiaohongshu.xiaohongshu_search
2025-08-27 14:26:39 - DEBUG - src.core.plugin_manager - plugin_manager.py:58 - _auto_discover_plugins - Auto-discovered plugin module imported: src.plugins.zhihu.zhihu_collection_list
```

### 使用RPC客户端调用插件

查看 `client_sdk/quick_start_rpc.py` 文件，它展示了如何使用RPC客户端以便捷方式调用服务程序中的插件：

```python
import asyncio
from client_sdk.rpc_client import EAIRPCClient
from client_sdk.params import TaskParams

async def main():
  # 创建RPC客户端
  client = EAIRPCClient(
    base_url="http://127.0.0.1:8008",  # 服务程序IP+端口
    api_key="testkey",  # 与服务程序约定的API密钥
    webhook_host="127.0.0.1",  # webhook订阅服务监听地址
    webhook_port=0,  # webhook订阅服务端口
  )

  try:
    # 启动客户端
    await client.start()
    print("✅ RPC客户端已启动")
    
    # 🤖 与AI聊天
    print("\n🤖 与AI元宝聊天...")
    chat_result = await client.chat_with_yuanbao(
        ask_question="你好，我是小星星",
        conversation_id=None,
        task_params=TaskParams(
            cookie_ids=["819969a2-9e59-46f5-b0ca-df2116d9c2a0"],
            close_page_when_task_finished=True,
        ),
    )
    if chat_result["success"]:
        print(f"AI回复: {chat_result.get('data')[0].get('last_model_message', 'N/A')}")
    else:
        print(chat_result["error"])

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

如果你只是想使用插件而不是自己开发插件，那接下来你只需要了解调用插件应该传入的参数是什么就可以，具体见`client_sdk/params.py`

#### TaskParams 通用配置

`TaskParams` 是所有插件的通用配置，包含浏览器和任务的基本设置：

```python
@dataclass
class TaskParams:
    headless: Optional[bool] = None
    cookie_ids: List[str] = field(default_factory=list)
    viewport: Optional[Dict[str, int]] = None
    user_agent: Optional[str] = None
    extra_http_headers: Optional[Dict[str, str]] = None
    close_page_when_task_finished: bool = False

    # Don't need [extra] field in client_sdk
```

**常用TaskConfig参数说明：**

- `headless` (bool): 是否无头模式运行浏览器，默认 `True`
- `cookie_ids` (List[str]): 使用的Cookie ID列表，从 `accounts/cookies.enc` 中读取
- `viewport` (Dict): 浏览器视口大小，格式 `{"width": 1280, "height": 800}`
- `user_agent` (str): 自定义User-Agent字符串
- `extra_http_headers` (Dict): 额外的HTTP请求头
- `close_page_when_task_finished` (bool): 任务完成后是否关闭页面，默认 `False`

#### ServiceParams 通用服务配置

`ServiceParams` 用于配置服务层的通用行为，特别是数据收集相关的设置：

```python
@dataclass
class ServiceParams:
    response_timeout_sec: float = 5.0
    delay_ms: int = 500
    queue_maxsize: Optional[int] = None
    scroll_pause_ms: int = 800
    max_idle_rounds: int = 2
    max_items: Optional[int] = 10000
    max_seconds: int = 600
    auto_scroll: bool = True
    scroll_mode: Optional[str] = None
    scroll_selector: Optional[str] = None
    max_pages: Optional[int] = None
    pager_selector: Optional[str] = None
    need_raw_data: bool = False
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
- `need_raw_data` (bool): 响应是否需要携带原始数据(采用Net服务时有效，抓取网页元素（Dom）的形式无效)

#### 好的，我来给 `SyncParams` 写一份和你提供的 `ServiceParams` 模板风格一致的文档说明：

---

#### SyncParams 数据同步配置

`SyncParams` 用于配置被动数据同步的行为，特别是 **停止条件** 和 **删除策略**，确保在数据采集或同步过程中能够智能地判断何时结束、如何处理删除记录。
（删除策略目前还未完成实现，目前用来检测是否有数据新增上很好用，例如收藏夹场景）
```python
@dataclass
class SyncParams:
    identity_key: str = "id"
    deletion_policy: str = "soft"
    soft_delete_flag: str = "deleted"
    soft_delete_time_key: str = "deleted_at"
    stop_after_consecutive_known: Optional[int] = None
    stop_after_no_change_batches: Optional[int] = None
    max_new_items: Optional[int] = None
    fingerprint_fields: Optional[Sequence[str]] = None
    fingerprint_key: str = "_fingerprint"
    fingerprint_algorithm: str = "sha1"
```

**常用 SyncParams 参数说明：**

* `identity_key` (str): 用于唯一标识记录的字段名，默认 `"id"`
* `deletion_policy` (str): 删除策略，默认 `"soft"`。
  * `"soft"`：逻辑删除（通过标记字段）
  * `"hard"`：物理删除（直接移除文档）
* `soft_delete_flag` (str): 标记软删除的字段名，默认 `"deleted"`
* `soft_delete_time_key` (str): 存储软删除时间戳的字段名，默认 `"deleted_at"`
* `stop_after_consecutive_known` (int): 当一个批次中出现指定数量的连续“已知项”时停止同步。例如设置为 `5`，当连续 5 条数据都是已同步记录时，任务结束
* `stop_after_no_change_batches` (int): 在连续若干个批次中没有新增或更新数据时停止同步。例如设置为 `3`，表示连续 3 个批次无变化就结束
* `max_new_items` (int): 当一次会话中新采集的数据量达到此上限时停止同步
* `fingerprint_fields` (List\[str]): 用于生成数据指纹的字段集合。如果为 `None`，则使用除内部 bookkeeping 字段外的所有字段
* `fingerprint_key` (str): 指纹存储字段名，默认 `"_fingerprint"`
* `fingerprint_algorithm` (str): 指纹算法，默认 `"sha1"`，可选 `"sha1"`, `"sha256"`

---


### 重要提示

1. **Cookie管理**: 首次使用任何插件都需要手动登录以保存Cookie。后续运行可以直接使用 `cookie_ids` 复用已保存的登录状态。`cookie_ids`可在登录后在日志输出中看到，**目前还未对cookie做管理上的优化！**

2. **数据存储**: 大部分插件都会将采集到的数据存储到本地文件中，请确保有足够的磁盘空间。

3. **频率控制**: 避免过于频繁的请求，这样也可以避免被检测和封帐号。

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

## 📚 插件文档

- **[插件 API 完整参考](./docs/plugins_api_reference.md)** - 所有插件的详细参数、返回值和使用示例
- **[插件快速参考表](./docs/plugins_quick_reference.md)** - 快速查找插件ID、方法名和关键参数
- **[小红书详情插件v3.0迁移指南](./docs/xiaohongshu_details_v3_migration.md)** - 从v2.0升级到v3.0的指南

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
更多深入内容，可查阅[开发者SOP](./docs/developer_sop.md)


## 贡献指南

欢迎贡献新插件或改进现有功能！贡献前，请阅读以下指南：

1. Fork 项目并创建特性分支
2. 遵循项目的代码风格和文档要求
3. 为新功能添加测试
4. 确保所有测试通过
5. 提交 Pull Request
