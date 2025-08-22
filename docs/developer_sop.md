# 开发者 SOP
[toc]

## 最佳实践（可直接照做）
* **数据采集分过程，不要一次就拿下详细数据！！！！**（这点最最最最最最关键！！！）
  * 比如小红书笔记数据采集，可以先通过瀑布流获取简略的笔记信息，一条笔记由note_id和xsec_token确定，你至少需要保证这两条数据到手。
  * 接下来，利用获取笔记详情插件，来不断的爬取笔记的详情数据！
* 订阅最小化：用精确正则命中目标 API，避免噪声；一站多口时订多条。
* 解析幂等：item 必须含稳定主键；关注字段变化时采用 fingerprint 合理取字段。
* 合理节流：scroll_pause_ms、delay_ms、max_idle_rounds 配合，既快又稳。
* 防封：随机 UA/Headers；慢动作/人类化滚动；限制并发；必要时 DOM 混合策略。
* 可观测性：在回调与 stop_decider 里打点（count、elapsed、exit reason），便于溯源。
* 清理资源：helper.stop()、解绑 bus、关闭页面；异常路径同样要回收。

## 0. 目标读者
* 仅“使用插件”的开发者：只需要用 RPC 客户端/REST 快速接入，阅读`README.md`即可
* 扩展能力的开发者：新增插件、沉淀服务、打磨同步与可靠性，同样需要先阅读`README.md`即可

## 1. 架构速读与阅读顺序
* 入口与生命周期：src/api/server.py（FastAPI、lifespan、Orchestrator/Scheduler 初始化）
* 客户端交互：src/client/rpc_client.py（topic/subscription 自动化、签名校验、Future 等待）
* 配置系统：src/config/*、config.example.json5（集中化配置与环境变量映射）
* 同步引擎：docs/data_sync/README.zh.md（PassiveSyncEngine 的使用方式）
* 其他：examples/*（从例子反推真实参数组合）

最佳实践：
* 遇到“为什么这么设计”，先对照你文档中的“分层说明”，再回到具体代码定位
* 所有“跨插件复用”的逻辑优先落服务层，插件仅做编排与场景 glue


## 2. 配置与参数（开发者视角）
* 服务端鉴权
    * 默认读取 EAI_API_KEY，客户端以 X-API-Key 头传入
    * 开发模式未设置时为开放访问；建议在团队/生产环境必须配置
* 浏览器与网络
    * headless 在本地关闭、CI/服务器开启
    * 需要代理时，通过 browser.proxy.* 注入（见 config.example.json5 与 BrowserConfig）
* 任务与服务
    * TaskConfig：围绕“浏览器/任务级别”参数
    * ServiceConfig & extra：围绕“数据采集策略与业务特性”参数
    * 客户端不需要显式构造 TaskConfig 对象，按键填入即可

最佳实践：
* 把“频率控制”和“超时策略”放在 ServiceConfig 中显式声明；避免隐式死循环
* 采集数据尽量使用 storage_file + PassiveSync，以便具备幂等与增量能力

## 3. 数据同步（PassiveSyncEngine）
* 适用场景：分页/滚动流式采集（首页、搜索页、收藏夹等）
* 能力：识别新增/更新；按阈值建议停止，避免浪费
* 当前限制：删除识别待完善，先以新增/更新为主

最佳实践：
* 选择稳定的 identity_key（如笔记 id）
* 启用 fingerprint_fields 只覆盖对业务有意义的字段，避免 HTML/时序噪声导致“假更新”
* 通过 stop_after_consecutive_known/stop_after_no_change_batches 保证会话可终止

## 4. 服务层与插件层的协作
* 原则：服务层沉淀“可复用能力”，插件专注“场景编排与入口路由”
* 示例：瀑布流采集器放在服务层（滚动、加载、提取、反爬控制），插件只决定去哪一个页面、如何组装参数

最佳实践：
* 服务层 API 要保持“平台无关/页面少耦合”；把 CSS Selector/特定接口路径集中管理
* 同一站内不同入口（首页/搜索/收藏）尽量共用一套服务能力，减少重复

## 5. 开发一个新插件（从 0 到 1）- 深入版
### 5.1 选择策略：网络监听 vs 直接 DOM 解析
* 网络监听（推荐优先）
    * 优点：结构化、稳定、性能好；避免复杂 DOM 解析；天然更贴近后端分页/游标语义。
    * 何时用：接口返回 JSON；列表/详情接口可直接拿数据；需要精确去重与增量。
* DOM 解析
    * 优点：无 API 也能用；对强前端渲染页面能兜底。
    * 何时用：接口受强校验/签名保护；前端异步渲染且可稳定选择器获取。
    * 风险与对策：易碎、慢、易被反爬 → 使用滚动节流、选择器断言、尽量提取语义稳定的属性；与网络监听组合使用更稳。

最佳实践：
* “能网就网，网不全再 DOM 补齐”。用 PassiveSync 做幂等与增量，避免重复开销。
* 把“滚动/翻页/节流/限速”集中给 ServiceConfig 调整，插件只做编排。


### 5.2 NetHelper 与回调（NetConsumeHelper + NetRuleBus）
* 角色分工
    * NetRuleBus：绑定 Page，用正则订阅 request/response，产出 ResponseView/RequestView 队列。
    * NetConsumeHelper：消费“合并队列”，应用校验、委托回调（on_before_response / on_response / parse_items / on_items_collected），把解析好的 items 放进状态并唤醒采集循环。
    * NetServiceDelegate：挂载到 Service，用于插入回调逻辑与定制解析。

关键代码（回调与消费主循环）：
```python
class NetConsumeHelper(Generic[T]):
    ...
    async def start(
        self,
        *,
        default_parse_items: DefaultParser[T],
        payload_ok: Optional[PayloadValidator] = None,
    ) -> None:
        if self._consumer:
            return
        self._consumer = asyncio.create_task(
            self._consume_loop(default_parse_items=default_parse_items, payload_ok=payload_ok)
        )

    async def _consume_loop(...):
        ...
        while True:
            self._consume_count += 1
            if self.delegate.on_before_response:
                await self.delegate.on_before_response(self._consume_count, self._extra, self.state)
            evt: MergedEvent = await self._merged_q.get()
            ...
            # 原始数据
            data = evt.view.data()
            ...
            # on_response 先观察原始响应
            if self.delegate.on_response and self.state:
                await self.delegate.on_response(evt.view, self.state)
            ...
            # 记录到 state.raw_responses / last_response
            if should_record and self.state:
                record_response(self.state, data, evt.view)
            ...
            # 优先用 delegate.parse_items，否则用默认 default_parse_items
            if self.delegate.parse_items:
                parsed = await self.delegate.parse_items(data)
            if parsed is None:
                parsed = await default_parse_items(payload)
            ...
            # on_items_collected 后处理并入 state.items，然后唤醒队列
            if self.delegate.on_items_collected:
                parsed = await self.delegate.on_items_collected(parsed, self._consume_count, self._extra, self.state)
            self.state.items.extend(parsed)
            await self.state.queue.put(parsed)
```

NetRuleBus 订阅与合并队列：
通过`subscribe_many`可以将多个订阅的接口请求合并到一起（似乎略显鸡肋），之后处理响应时需要区分到底是哪一个url

ResponseView/RequestView：
当响应到达之后，_preloaded会自动赋值为解析后的数据，如果返回json数据，则可以通过data方法直接拿到
```python
class ResponseView:
    def __init__(self, original: Response, preloaded: Any) -> None: ...
    def data(self) -> Any:
        return self._preloaded
```

### 5.3 Service 层内容一览（做什么、怎么扩展）
BaseSiteService + ServiceConfig（浏览/滚动/限速等通用参数）
```python
@dataclass
class ServiceConfig:
    response_timeout_sec: float = 5.0
    delay_ms: int = 500
    queue_maxsize: Optional[int] = None
    concurrency: int = 1
    scroll_pause_ms: int = 800
    max_idle_rounds: int = 2
    max_items: Optional[int] = None
    max_seconds: int = 600
    auto_scroll: bool = True
    scroll_mode: Optional[str] = None
```

* NetService + NetServiceDelegate（网络驱动型服务的回调集合）
    * on_before_response(consume_count, extra, state)
    * on_response(response_view, state)
    * should_record_response(payload, response_view) → 控制是否入 raw_responses
    * parse_items(payload) → 返回 List[T] 或 None
    * on_items_collected(items, consume_count, extra, state) → 二次加工/去重/补充字段
* NetCollectionState（本次会话状态）
    * items/raw_responses/last_response_view/stop_decider/queue
    * 使用 record_response(state, payload, view) 进行统一记录

* scroll_helper（滚动/选择器模式）
    * 通过 scroll_mode/scroll_selector/pager_selector 与 scroll_page_once 控制滚动或分页


### 5.4 通用采集主循环：run_generic_collection
入口与关键参数：
```python
async def run_generic_collection(
    *,
    extra_config: Optional[Dict[str, Any]] = None,
    page: Page,
    state: Any,
    max_items: int,
    max_seconds: int,
    max_idle_rounds: int,
    auto_scroll: bool,
    scroll_pause_ms: int,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick: Optional[OnTick] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick_start: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
    key_fn: Optional[Callable[[T], Optional[str]]] = None,
) -> List[T]:
```
循环行为要点（idle 检测、超时、滚动、stop_decider）：
```python
elapsed = loop.time() - start_ts
if elapsed >= max_seconds: break
if len(state.items) >= max_items: break
...
# on_tick 未显式返回新增数时，用 len(state.items) 的增量推断
...
if idle_rounds >= max_idle_rounds: break
...
if state.stop_decider:
    stop_decision = await result
    if stop_decision.should_stop:
        break
...
if auto_scroll:
    await (on_scroll() if on_scroll else _scroll_page_once(page, pause_ms=scroll_pause_ms))
```
网络驱动统一入口（把“事件队列唤醒”转为 on_tick）：
当响应到达时，会往state.queue里put数据，这样state.queue.get()就能够获知数据到达
```python
async def run_network_collection(state, cfg, *, goto_first=None, on_scroll=None, on_tick_start=None, key_fn=None, network_timeout=5.0) -> List[T]:
    async def on_tick() -> Optional[int]:
        await state.queue.get()
        state.queue.task_done()
        return 0  # 新增数用 len(items) 增量推断
    async def default_scroll(): await _scroll_page_once(state.page, pause_ms=cfg.scroll_pause_ms)
    return await run_generic_collection(..., on_tick=on_tick, on_scroll=on_scroll or default_scroll, ...)
```

### 5.5 从 0 到 1：最小网络监听插件“套路”
* 目标：在某站点“搜索页”抓取列表项
* 步骤：
    * 维护正则订阅清单：[(".*api/search.*", "response")]
    * 建立 NetCollectionState(page, asyncio.Queue())
    * 构造 NetConsumeHelper(state=..., delegate=NetServiceDelegate())
    * 定义 payload_ok → 校验返回结构
    * 实现 delegate.parse_items(payload) → 提取成标准 Item 列表
    * 可选：on_before_response/on_response/on_items_collected
    * helper.bind(page, patterns) → helper.start(default_parse_items, payload_ok)
    * run_network_collection(state, cfg, goto_first=navigate_to_search, on_tick_start=...)
    * 结束后 await helper.stop()

具体可以参考一个service示例


### 6.6 StopDecider（何时优雅停止）
* 在 state.stop_decider 注入：以“批增量 + 时间”做决策，返回 StopDecision(should_stop, reason)
* 常见策略：
    * 连续空转 N 轮（新项目 0）停止
    * 连续命中已知 ID 过多停止
    * 本会话累计新增到上限停止
    * 观察 payload.cursor 或 has_more 终止条件





