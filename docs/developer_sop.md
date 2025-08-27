# 开发者 SOP
[toc]

## 最佳实践
* **数据采集分过程，不要一次就拿下详细数据！！！！**（这点最最最最最最关键！！！）
  * 比如小红书笔记数据采集，可以先通过瀑布流获取简略的笔记信息，一条笔记由note_id和xsec_token确定，你至少需要保证这两条数据到手。
  * 接下来，利用获取笔记详情插件，来不断的爬取笔记的详情数据！

## 0. 目标读者
* 仅“使用插件”的开发者：只需要用 RPC 客户端/REST 快速接入，阅读`README.md`即可
* 扩展能力的开发者：新增插件、沉淀服务、打磨同步与可靠性，同样需要先阅读`README.md`即可

## 1. 我们的爬虫是如何运作的（重要）

我们的爬虫核心基于 **Playwright 自动化测试工具**。通过它，我们可以模拟真实用户打开网页，并利用其对 **DOM 操作** 和 **网络请求/响应监听** 的能力，构建所需的爬取功能。

换句话说，我们的对象始终是网页本身。这里并不存在一个统一的 API，可以一次性直接获取到所需的数据（例如某网站的收藏内容）。一切都是 **所见即所得** ——我们所要做的，就是抓取页面数据并将结果提取出来。

为了快速上手，让我们先来看看使用自动化爬取时需要考虑的几个关键问题：

* **你需要的数据是什么？**
* **哪些页面包含这些数据？**
* **是否需要登录？**（有些网站无需登录，可跳过）

  * 登录入口在哪里？
  * 登录方式是什么？（目前仅支持手动登录）
  * 如何判断登录成功？
* **登录成功后，如何进入目标页面？**

  * 目标页面地址是什么？
* 打算用哪种方式来爬取数据？

  * **监听网络响应（推荐）**

    * 目标数据在哪个 API 请求里？（建议全局搜索，很快能找到）
    * 如何监听目标 API？
    * 如何解析 API 返回的数据？
  * **解析 DOM（备用方案）**

    * 如何从页面元素中提取数据？

当我们需要把爬虫扩展成一个 **插件/服务** 时，还要进一步思考：

* 是否需要让用户输入参数？（如：指定某个博主的笔记）
* 哪些参数需要用户提供？（如：博主 ID）
* 参数该如何定义与使用？（本项目已提供最佳实践）

---

### 项目中尚未实现但值得探索的问题

* 页面是否支持复用？如何优化复用能力？
* Cookie 管理是否可以更细致？哪些字段最关键？
* 是否需要前端监控界面？
* 能否支持在浏览器直接运行？（让没有电脑的用户也能使用）
* 更多 **AI 插件** 的接入，以增强数据处理能力：
  * 图片 OCR
  * 文本抽取（LangExtract）
  * 深度研究（Deep Research）
  * ……

---

我们的目标并不是停留在“数据采集”层面，而是打造一个 **数据基础层**：让数据不再孤立在不同平台，而是能通过二次接口统一展现。

想一想，你每天要打开多少个网页、多少个 App？你曾经收藏过的内容又有多久没有再看过？

未来更重要的，不仅是“能不能拿到数据”，而是 **如何用好这些数据**。AI 代表着更先进的生产力：在数据采集之上，如何进一步 **分析、总结、转化为价值**，才是更值得探索的方向。


## 2. 为什么需要做插件（Plugin）/服务（Service）分层
我是这样定义Plugin和Service的
* Plugin：它可以管理一个或多个Service，主要的职责是推进服务的运行，负责控制：
  * 应该打开哪个页面？
  * 如何与用户提供的参数作配合，进入到需要的页面？
  * 服务推进的速度应该是怎么样的？
  * 管控着服务的爬取周期（通过Delegate）
  * 什么情况下应该优雅的关闭服务？
  * 等等各种比较大的问题
* Service：它主要负责某一个细微点的执行，
  * 监听一个网络响应
  * 负责将api数据解析成需要的格式

这样设计之下，有几个好处：
* 职责清晰、明确，业务不容易混乱
* Service具备复用的潜力

## 3. 从0开始开发插件

延续前面的思路，我们来实际走一遍插件开发流程。接下来以 **小红书收藏笔记获取插件** 为例，带大家从零开始构建。我们的插件代码放在 `src/plugins/xiaohongshu` 目录下。

---

### 3.1 明确数据需求

首先要解决的问题是：**我们到底需要哪些数据？**

在这里，我们的目标是获取小红书收藏笔记的 **详细信息**。所以第一步，就是定义清晰的数据需求。

创建文件 `src/services/xiaohongshu/models.py`（为保证复用性，本项目将其实际放在 `src/services/models.py`）。

```python
@dataclass
class UserInfo:
    user_id: str
    username: str
    avatar: str
    xsec_token: Optional[str] = None
    gender: Optional[str] = None
    is_following: Optional[bool] = None
    is_followed: Optional[bool] = None
    user_type: Optional[str] = None


@dataclass
class AuthorInfo(UserInfo):
    pass


@dataclass
class NoteStatistics:
    like_num: str      # 点赞数量
    collect_num: str   # 收藏数量
    chat_num: str      # 评论数量


@dataclass
class VideoInfo:
    duration_sec: int
    src: str
    id: str


@dataclass
class NoteDetailsItem(WithRaw):
    id: str
    xsec_token: str
    title: str
    desc: str
    author_info: AuthorInfo
    tags: List[str]
    date: str
    ip_zh: str
    comment_num: str
    statistic: NoteStatistics
    images: Optional[list[str]]
    video: Optional[VideoInfo]
    timestamp: str
```

规则很简单：需要什么数据，就定义什么字段。

---

### 3.2 哪些页面包含数据

这个问题并不复杂。小红书收藏页面就是我们需要的入口，相信大家都很熟悉。

---

### 3.3 是否需要登录

* **登录入口**： [https://www.xiaohongshu.com/login](https://www.xiaohongshu.com/login)
* **登录方式**：手动扫码登录，登录态有效期较长，可以反复使用。
* **如何判断登录成功？**
  登录成功后会跳转到首页，用户头像会显示出来。我们选择头像元素的选择器 `.reds-img-box` 来作为登录成功的判断依据。

---

### 3.4 登录成功后，如何进入目标页面

小红书的用户界面 URL 格式中包含 **用户 ID**。虽然我们可以通过监听 API 来获取，但对于只需要一个 ID 的场景来说有些繁琐。于是我们采用更直接的方式：用 **Playwright 控制按钮点击**。

1. 点击用户头像，进入用户个人页面。
2. 再点击“收藏”，进入收藏标签页。

---

### 3.5 爬取数据的方式

进入收藏页后，打开开发者工具（F12），切换到 **网络 (Network)** 标签，再刷新页面，就能找到一个 API ——它返回了收藏笔记的 **简略信息**。

这时候问题来了：
简略信息 ≠ 详细信息。
要拿到完整内容，就得逐条点开笔记详情，这样一来就需要处理 DOM，写起来很繁琐。

但是，稍微分析一下 URL 规则，就能找到更优解：

笔记详情页 URL 格式：

```
https://www.xiaohongshu.com/explore/{noteId}?xsec_token={NoteXSecToken}&xsec_source=pc_feed
```

也就是说，只要拿到 **noteId** 和 **xsec\_token**，就能拼出笔记详情页的地址。幸运的是，这两个参数正好包含在简略信息里。

因此，策略立刻调整为 **两步走**：

1. 获取收藏笔记的简略信息。
2. 根据简略信息中的 `noteId` 和 `xsec_token`，再去获取对应的详细信息。

这样不仅更高效，还能避免复杂的 DOM 操作。

---

### 3.6 最终规划

我们需要开发两个插件：

1. **收藏笔记简略信息插件** ——获取收藏笔记的基础信息（含 noteId 和 xsec\_token）。
2. **笔记详情信息插件** ——利用简略信息中的参数，抓取笔记的完整内容。

> 为什么不是两个独立服务？
> 因为插件可以更快迭代，时间成本更低。同时，错误恢复等问题可以放在更高层去做。


下一节开始，我们正式进行插件的开发
---

## 收藏笔记的简略信息插件

简略信息本身就是一个新的数据需求，因此我们需要先为它定义数据结构。

```python
@dataclass
class NoteBriefItem(WithRaw):
    id: str
    xsec_token: str
    title: str
    author_info: AuthorInfo
    statistic: NoteStatistics
    cover_image: str
```

定义好数据模型之后，我们就可以着手编写 Service 逻辑。创建文件：
`src/services/xiaohongshu/note_brief_net.py`

在 Service 中，我们需要依次解决几个核心问题：

1. **监听哪个 API？如何监听？**
2. **如何解析出需要的数据？**

---

#### 1. 如何监听 API

项目中已经封装好了一个工具类 `net_helper.py`，位于
`src/services/net_consume_helpers.py`。

它可以帮助我们快速完成 **网络请求监听 + 数据消费**，下面给出一个使用示例：

```python
class XiaohongshuNoteBriefNetService(NetService[NoteBriefItem]):
    """
    小红书瀑布流笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[NoteBriefItem](page=page, queue=asyncio.Queue())

        # 实例化 NetConsumeHelper，传入 state 和回调 delegate
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)

        # 绑定要监听的 API
        await self._net_helper.bind(page, [
            (r".*/note/collect/page/*", "response"),
        ])

        # 启动监听并传入解析函数
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper)

        await super().attach(page)

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[NoteBriefItem]:
        items_payload = payload.get("data").get("notes", [])
        return parse_brief_from_network(items_payload, raw_data=self._inject_raw_data(payload))
```

**说明：**

* `self._net_helper = NetConsumeHelper(...)`：负责注册网络监听逻辑。
* `bind(...)`：定义监听规则，这里使用正则 `r".*/note/collect/page/*"` 来匹配收藏 API，并指定监听 **响应** 而不是请求。
* `start(...)`：真正启动监听，并指定默认解析函数 `_parse_items_wrapper`。

---

#### 2. 为什么需要 run\_network\_collection？

虽然网络监听已经完成，但 Service 并没有结束。我们还需要实现 `invoke` 方法：

```python
class XiaohongshuNoteBriefNetService(NetService[NoteBriefItem]):
    """
    小红书瀑布流笔记抓取服务 - 通过监听网络实现，而非解析 Dom
    """

    async def invoke(self, extra_params: Dict[str, Any]) -> List[NoteBriefItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(
            self.page,
            service_params=self._service_params,
            pause_ms=pause,
            extra=extra_params
        )

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            delegate=self.loop_delegate,
        )
        return items
```

`invoke` 方法供插件调用，它接收参数并返回一个数据列表。
其核心依赖是 `run_network_collection`，它的作用是：

* **为什么需要它？**

  * 项目采用 **协程** 实现，主协程执行`run_network_collection`，而监听 API 的逻辑运行在另一个协程循环中，而 `invoke` 需要同步拿到数据。
  * 为了桥接两者，`run_network_collection` 会新开一个 loop 来消费队列数据。
* **如何配合？**

  * 网络监听协程把抓到的数据塞入 `asyncio.Queue`。
  * `run_network_collection` 则持续从队列中取数据，一旦有数据，就立即触发解析和处理。

这两个循环（监听循环 + 消费循环）是本项目的 **核心机制**，理解了它，整个 Service 的执行模型就清晰了。

---

📌 **总结流程**

**数据流转：网络监听 → 数据入队 → run\_network\_collection 消费队列 → invoke 返回结果**



👌 好的，我帮你把这一部分润色成 **清晰、结构化的技术说明**，既保持原意，又让开发者读起来更顺畅：

---

### 数据解析逻辑

当网络数据到来后，下一步就是**解析响应内容**。
通过分析 API 的 JSON 格式，我们可以很容易地写出数据解析函数：

```python
def parse_brief_from_network(resp_items: List[Dict[str, Any]], raw_data: Any) -> List[NoteBriefItem]:
    """
    从网络响应中解析笔记简要信息

    Args:
        resp_items: 网络响应中的笔记列表
        raw_data: 原始数据

    Returns:
        List[NoteBriefItem]: 解析后的笔记简要信息列表
    """
    results: List[NoteBriefItem] = []
    for note_item in resp_items or []:
        try:
            id = note_item["note_id"]
            title = note_item.get("display_title")
            xsec_token = note_item.get("xsec_token")

            # 作者信息
            user = note_item.get("user", {})
            author_info = AuthorInfo(
                username=user.get("nickname"),
                avatar=user.get("avatar"),
                user_id=user.get("user_id"),
                xsec_token=user.get("xsec_token"),
            )

            # 互动数据
            interact = note_item.get("interact_info", {})
            statistic = NoteStatistics(
                like_num=str(interact.get("liked_count", 0)),
                collect_num=None,
                chat_num=None,
            )

            # 封面图
            cover_image = note_item.get("cover", {}).get("url_default")

            # 封装为 NoteBriefItem
            results.append(
                NoteBriefItem(
                    id=id,
                    xsec_token=xsec_token,
                    title=title,
                    author_info=author_info,
                    statistic=statistic,
                    cover_image=cover_image,
                    raw_data=note_item,
                )
            )
        except Exception as e:
            logger.error(f"解析笔记信息出错：{str(e)}")
    return results
```

相比 DOM 解析，这种方式更加直观和稳定，极大降低了解析难度。

---

### 插件开发

完成 Service 后，下一步就是编写插件。
新建文件：
`src/plugins/xiaohongshu/xiaohongshu_favorites_brief.py`

#### 插件基本定义

```python
class XiaohongshuNoteBriefPlugin(BasePlugin):

    # 插件唯一标识
    PLUGIN_ID: str = PLUGIN_ID
    PLUGIN_NAME: str = __name__
    PLUGIN_VERSION: str = "2.0.0"
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu note brief info plugin (service-based v{PLUGIN_VERSION})"
    PLUGIN_AUTHOR: str = ""

    # 平台 / 登录配置（供 BasePlugin 的通用登录逻辑使用）
    LOGIN_URL = "https://www.xiaohongshu.com/login"
    PLATFORM_ID = "xiaohongshu"
    LOGGED_IN_SELECTORS = [
        ".reds-img-box",
    ]
```

其中 `LOGIN_URL`、`PLATFORM_ID`、`LOGGED_IN_SELECTORS` 并非仅仅是说明信息，它们会被 **login\_helper** 使用。
login\_helper 对登录流程进行了简单封装，插件只需提供少量配置，即可完成：

* 登录检测
* Cookie 注册
* 登录态保持

---

#### fetch：插件的入口方法

每个插件必须实现 `fetch` 方法，它是插件运转的起点：

```python
async def fetch(self) -> Dict[str, Any]:

    await self._ensure_logged_in()
    self._note_brief_net_service.set_params(self.task_params.extra)
    try:
        # 加载历史存储（避免重复抓取）
        await self._note_brief_delegate.load_storage_from_data(self.task_params.extra.get("storage_data", {}))

        # 核心逻辑：抓取收藏笔记
        briefs_res = await self._collect_briefs()

        if briefs_res["success"]:
            diff = self._note_brief_delegate.get_diff()
            logger.info(f"diff: {diff.stats()}")

            full_data = self._note_brief_delegate.get_storage_data()
            return {
                "success": True,
                "data": full_data,
                "count": len(full_data),
                "plugin_id": self.PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }

        raise Exception(briefs_res["error"])

    except Exception as e:
        logger.error(f"Fetch operation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "plugin_id": self.PLUGIN_ID,
            "version": self.PLUGIN_VERSION,
        }
```

核心逻辑 `_collect_briefs`：

1. 确认已登录。
2. 进入用户收藏页面。
3. 调用 `note_brief_net_service` 启动 Service，收集笔记数据。
4. 将结果序列化为 JSON。

```python
async def _collect_briefs(self) -> Dict[str, Any]:
    if not self._note_brief_net_service:
        raise RuntimeError("Services not initialized. Call setup() first.")

    async def goto_favorites():
        await self.page.click('.user, .side-bar-component')
        await asyncio.sleep(1)
        await self.page.click(".sub-tab-list:nth-child(2)")

    try:
        await goto_favorites()
        items = await self._note_brief_net_service.invoke(self.task_params.extra)

        # 转换为字典，便于 JSON 输出
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} favorite items")

        return {
            "success": True,
            "data": items_data,
            "count": len(items_data),
        }

    except Exception as e:
        ...
```

---

### 插件注册

插件最后需要显式注册：

```python
@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuNoteBriefPlugin:
    p = XiaohongshuNoteBriefPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page / account_manager）
    p.set_context(ctx)
    return p
```

这样，插件即可被框架正确识别和加载。

---

📌 **总结流程**

* **fetch**：插件入口 → 确认登录 → 调用 `_collect_briefs`
* **\_collect\_briefs**：进入收藏页 → 调用 Service → 收集并序列化数据
* **Service**：监听 API → 解析 JSON → 返回简略信息

## 笔记详情信息插件


