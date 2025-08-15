## 使用指南（基于 `xhs_example_v2.py`）

本指南围绕 `xhs_example_v2.py` 及其导入的核心模块，帮助你快速完成安装、登录与任务调度，获取小红书收藏流的数据。无需关注 `xhs_example.py`。

### 适用范围
- **仅覆盖** `xiaohongshu_v2` 插件和它使用的服务：`note_net`（详情流）、`note_brief_net`（摘要流/卡片）、`comments`（评论）。
- **已稳定支持的 task_type**：`favorites` 与 `briefs`（收藏流采集），`comments`（评论采集）。
- 代码中存在占位但未初始化的能力：`search` 与 `details` 尚未注入对应服务，建议暂不使用。

### 环境要求
- **Python**: 3.9+（推荐 3.10/3.11）
- **系统**: Windows 10/11，已安装 Microsoft Edge（或改用 Chrome）
- **依赖**: Playwright、cryptography、httpx、pytest 相关等（见 `requirements-dev.txt`）

### 安装
- 安装依赖：
```bash
pip install -r requirements-dev.txt
python -m playwright install
```
- 如使用本机 Edge 控制浏览器（默认 `channel="msedge"`），可不安装浏览器二进制；如改用 Chrome，将 Orchestrator 的 `channel` 改为 `"chrome"`。

### 首次运行与登录
- 运行示例（会启动浏览器，首轮需手动登录）：
```bash
python xhs_note_brief.py
```
- 首次运行流程：
  - 系统初始化 `EverythingAsInterface`，本地创建 `accounts/` 与 `data/` 目录。
  - 调度器添加 `xiaohongshu_v2` 任务，默认每 5 分钟执行一次。
  - 首次无 Cookie 时，插件会引导你打开登录页；完成登录后系统自动保存 Cookie 到 `accounts/cookies.enc`（加密存储）。
  - 控制台会打印“Cookie 已保存: <cookie_id>”。将该 `cookie_id` 复制到任务配置的 `cookie_ids`，后续运行可免登录。

- 二次运行（免登录）：
  - 在 `TaskConfig(cookie_ids=[...])` 中填写刚才保存的 `cookie_id`，程序会自动注入 Cookie 并校验是否已登录。

### 任务与调度模型
- `Scheduler.add_task(plugin_id="xiaohongshu_v2", interval=300, config=TaskConfig(...))`
  - **interval**：单位秒。
  - 任务回调将数据发布到订阅系统的主题，`on_new_favorite` 示例会打印新增收藏条目标题。
- 浏览器编排由 `Orchestrator` 负责（Playwright）。示例中：
  - `await orchestrator.start(headless=False)`：可改成 `True` 实现无头模式。
  - 如需代理：`await orchestrator.start(proxy={"server": "http://host:port", "username": "...", "password": "..."})`。

### 可用任务类型与关键配置

- 通用配置容器：`TaskConfig`
  - 常用字段：`headless`、`cookie_ids`、`viewport`、`user_agent`、`extra_http_headers`、`interval`
  - 插件自定义字段放在 `extra` 中（字典）

下面的字段是自己写的Service制定的，目前小红书v2插件中组合了多个Service，因此用了task_type，其他的插件不一定需要
- `task_type="favorites"`（详情流，暂时用不了）
  - 返回项类型：`NoteDetailsItem`
  - 关键 `extra`：
    - `max_items`：最大采集条数（默认 1000）
    - `max_seconds`：最大持续秒数（默认 600）
    - `max_idle_rounds`：空转轮数上限（默认 2）
    - `auto_scroll`：是否自动滚动（默认 True）
    - `scroll_pause_ms`：滚动暂停毫秒（默认 800）
    - 可选停止条件：`stop_on_tags`、`stop_on_author`、`stop_on_title_keywords`
  - 站点导航：自动点击进入“收藏”页（依赖选择器，站点更新可能需调整）

- `task_type="briefs"`（摘要卡片流，已完成）
  - 返回项类型：`NoteBriefItem`
  - `extra` 支持同上（滚动、限额、空转轮数等）
  - 站点导航：同“收藏”页
  - 注：当前实现的返回 JSON 中 `task_type` 字段值为 `"favorites"`（实现细节），不影响数据内容。

- `task_type="comments"`（评论，还未实现）
  - 必填：`extra.note_id`（笔记 ID）
  - 可选：`max_comment_pages`、`comment_delay_ms`
  - 返回项类型：`CommentItem`
  - 注意：示例代码里打开详情页与翻页为占位方法（`_open_note_and_show_comments` / `_load_next_comments_page`）；如要真实抓取需在 `src/services/xiaohongshu/comments.py` 中补齐触发逻辑（点击“评论”按钮/“更多评论”）。

### 最小可用示例（一键跑通收藏摘要）
```python
# 片段示意：将 xhs_note_brief.py 中 TaskConfig 的 extra 改为更小量测试
TaskConfig(
    cookie_ids=["<你的cookie_id>"],  # 首次登录后在控制台看见
    extra={
        "task_type": "briefs",      # 或 "favorites"
        "max_items": 20,
        "max_seconds": 120,
        "scroll_pause_ms": 600
    }
)
```

### 控制浏览器与代理（可选）
```python
# 用 Chrome 而非 Edge
orchestrator = Orchestrator(channel="chrome")
await orchestrator.start(headless=True)  # 无头运行

# 走代理
orchestrator = Orchestrator(proxy={"server": "http://127.0.0.1:7890"})
await orchestrator.start(headless=False)
```

### 返回数据结构（示例）
- `briefs`：
```json
{
  "success": true,
  "data": [
    {
      "id": "xxxx",
      "xsec_token": "xxxx",
      "title": "标题",
      "author_info": {"user_id":"...", "username":"...", "avatar":"...", "xsec_token":"..."},
      "statistic": {"like_num":"123", "collect_num":null, "chat_num":null},
      "cover_image": "https://..."
    }
  ],
  "count": 1,
  "plugin_id": "xiaohongshu_v2",
  "version": "2.0.0",
  "task_type": "favorites"
}
```
- `favorites`（详情流，字段更丰富，如 `images`、`ip_zh` 等）与 `comments` 返回格式类似，仅数据项结构不同。

### 常见问题与排查
- **插件未找到或未注册**：确认已导入 `src/plugins/xiaohongshu_v2.py`（示例里 `from src.plugins.xiaohongshu_v2 import XiaohongshuV2Plugin` 会触发注册）。
- **需要重新登录**：控制台出现 “检测到需要重新登录”，按提示在浏览器中完成登录；成功后会再次保存新的 Cookie ID。
- **Cookie 未生效**：确认 `cookie_ids` 为有效且未过期；`AccountManager` 会合并与校验，80% 以上过期会视为失效。
- **浏览器无法启动或白屏**：运行 `python -m playwright install`；Edge 未安装时，改用 `channel="chrome"` 并确保本机有 Chrome。
- **页面结构变化导致采集不到数据**：收藏页点击路径使用选择器：`.user, .side-bar-component` → `.sub-tab-list:nth-child(2)`。如站点更新需在 `XiaohongshuV2Plugin` 中调整。

### 目录与持久化
- `accounts/`：加密存储 Cookie（`cookies.enc`），平台定义（`platforms.json`）
- `data/`：你可在任务回调中自行落地 JSON/CSV/DB
- `everything-as-an-interface.log`：运行日志

### 安全提示
- `EverythingAsInterface(config={"master_key": "your-secret-key"})` 用于本地 Cookie 加密；生产请安全保存主密钥，并避免硬编码。


