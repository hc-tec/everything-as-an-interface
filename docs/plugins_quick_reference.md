# 插件快速参考表

快速查找插件ID、方法名和关键参数。

## 📋 所有可用插件

| 插件名称 | 插件ID | RPC方法名 | 版本 | 平台 |
|---------|--------|----------|------|------|
| 小红书收藏夹简略 | `xiaohongshu_favorites_brief` | `get_favorite_notes_brief_from_xhs()` | v2.0 | 小红书 |
| 小红书笔记详情 | `xiaohongshu_details` | `get_note_detail_from_xhs()` | v3.0 | 小红书 |
| 小红书笔记搜索 | `xiaohongshu_search` | `search_notes_from_xhs()` | v2.0 | 小红书 |
| 小红书收藏夹列表 | `xiaohongshu_collection_list` | - | v1.0 | 小红书 |
| B站收藏夹列表 | `bilibili_collection_list` | `get_collection_list_from_bilibili()` | v1.0 | Bilibili |
| B站收藏夹视频 | `bilibili_collection_videos` | `get_collection_list_videos_from_bilibili()` | v1.0 | Bilibili |
| B站视频详情 | `bilibili_video_details` | `get_video_details_from_bilibili()` | v1.0 | Bilibili |
| 知乎收藏夹列表 | `zhihu_collection_list` | `get_collection_list_from_zhihu()` | v1.0 | 知乎 |
| 元宝AI聊天 | `yuanbao_chat` | `chat_with_yuanbao()` | v1.0 | AI |
| PaddleOCR | `paddle_ocr` | `call_paddle_ocr()` | v1.0 | OCR |

## 🔍 按平台分类

### 小红书 (Xiaohongshu)

```python
# 获取收藏夹简略信息（支持增量同步）
await client.get_favorite_notes_brief_from_xhs(
    storage_data="[]",
    collection_id=None,  # 可选：指定收藏夹
)

# 获取单个笔记详情
await client.get_note_detail_from_xhs(
    note_id="xxx",
    xsec_token="yyy",
    wait_time_sec=3,
)

# 搜索笔记
await client.search_notes_from_xhs(
    keywords=["关键词"],
)
```

### Bilibili

```python
# 获取收藏夹列表
await client.get_collection_list_from_bilibili(
    user_id=None,
)

# 获取收藏夹视频（支持增量同步）
await client.get_collection_list_videos_from_bilibili(
    collection_id="123456",
    storage_data="[]",
)

# 获取视频详情
await client.get_video_details_from_bilibili(
    bvid="BV1xx411c7XZ",
)
```

### 知乎 (Zhihu)

```python
# 获取收藏夹列表
await client.get_collection_list_from_zhihu(
    user_id=None,
)
```

### AI聊天

```python
# 与元宝AI对话
await client.chat_with_yuanbao(
    ask_question="你好",
    conversation_id=None,  # 可选：继续会话
)
```

### OCR

```python
# 图像文字识别
await client.call_paddle_ocr(
    image_path_abs_path="/path/to/image.jpg",
    lang="ch",
)
```

## 📊 参数对照表

### 必需参数

| 插件 | 必需参数 | 类型 | 说明 |
|------|----------|------|------|
| xiaohongshu_details | `note_id` | str | 笔记ID |
| | `xsec_token` | str | 安全令牌 |
| xiaohongshu_search | `search_words` | str | 搜索关键词 |
| bilibili_collection_videos | `collection_id` | str | 收藏夹ID |
| bilibili_video_details | `bvid` | str | 视频BV号 |
| yuanbao_chat | `ask_question` | str | 提问内容 |
| paddle_ocr | `image_path_abs_path` | str | 图片绝对路径 |

### 可选参数速查

| 参数名 | 默认值 | 说明 | 适用插件 |
|--------|--------|------|----------|
| `storage_data` | `[]` | 已存储数据（增量同步） | 收藏夹类 |
| `user_id` | `None` | 用户ID | 大部分平台插件 |
| `collection_id` | `None` | 收藏夹ID | 小红书收藏夹 |
| `conversation_id` | `None` | 会话ID | 元宝AI |
| `wait_time_sec` | `3` | 页面加载等待时间 | 笔记详情 |
| `lang` | `"ch"` | 识别语言 | OCR |

## 🔧 通用参数快速配置

### TaskParams（必需配置）

```python
from client_sdk.params import TaskParams

# 最小配置（必需）
TaskParams(cookie_ids=["your-cookie-id"])

# 完整配置
TaskParams(
    headless=True,  # 无头模式
    cookie_ids=["uuid"],  # Cookie列表
    viewport={"width": 1280, "height": 800},
    close_page_when_task_finished=False,
)
```

### ServiceParams（常用配置）

```python
from client_sdk.params import ServiceParams

# 常用配置
ServiceParams(
    max_items=100,  # 最大条数
    scroll_pause_ms=800,  # 滚动暂停
    response_timeout_sec=5.0,  # 网络超时
    max_seconds=600,  # 最大执行时间
)
```

### SyncParams（增量同步）

```python
from client_sdk.params import SyncParams

# 增量同步配置
SyncParams(
    stop_after_consecutive_known=10,  # 连续10个已知项停止
    max_new_items=50,  # 最多新增50项
)
```

## 📤 返回值速查

### 标准格式

```python
{
    "success": True/False,
    "plugin_id": "插件ID",
    "plugin_version": "版本号",
    "timestamp": "时间戳",
    "data": {...}  # 或 "error": "错误信息"
}
```

### 数据结构速查

| 插件类型 | 返回数据结构 |
|---------|-------------|
| 收藏夹简略（支持sync） | `{data: [...], count: N, added: {...}, updated: {...}}` |
| 笔记详情 | `{id, title, desc, author_info, tags, images, ...}` |
| 搜索结果 | `[{id, title, author_info, cover_image, ...}, ...]` |
| 列表 | `[{id, title, description, item_count, ...}, ...]` |
| AI聊天 | `[{conversation_id, question, answer, ...}]` |
| OCR | `{text: "识别文本", lines: [...], image_info: {...}}` |

## 🎯 常见场景快速上手

### 场景1：首次获取收藏夹

```python
result = await client.get_favorite_notes_brief_from_xhs(
    storage_data="[]",  # 空数组
    task_params=TaskParams(cookie_ids=["uuid"]),
    service_params=ServiceParams(max_items=100),
)
```

### 场景2：增量同步收藏夹

```python
# 传入上次的全量数据
result = await client.get_favorite_notes_brief_from_xhs(
    storage_data=previous_data,  # 上次的 data["data"]
    task_params=TaskParams(cookie_ids=["uuid"]),
    sync_params=SyncParams(stop_after_consecutive_known=10),
)
```

### 场景3：批量获取笔记详情

```python
for note in notes:
    detail = await client.get_note_detail_from_xhs(
        note_id=note["id"],
        xsec_token=note["xsec_token"],
        task_params=TaskParams(cookie_ids=["uuid"]),
    )
    await asyncio.sleep(2)  # 延迟避免限流
```

### 场景4：搜索并获取详情

```python
# 1. 搜索
search_result = await client.search_notes_from_xhs(
    keywords=["咖啡馆"],
    task_params=TaskParams(cookie_ids=["uuid"]),
)

# 2. 获取详情
for note in search_result["data"][:10]:  # 只取前10个
    detail = await client.get_note_detail_from_xhs(
        note_id=note["id"],
        xsec_token=note["xsec_token"],
        task_params=TaskParams(cookie_ids=["uuid"]),
    )
```

### 场景5：多轮AI对话

```python
# 新对话
r1 = await client.chat_with_yuanbao(
    ask_question="你好",
    task_params=TaskParams(cookie_ids=["uuid"]),
)

# 继续对话
conv_id = r1["data"][0]["conversation_id"]
r2 = await client.chat_with_yuanbao(
    ask_question="请帮我写诗",
    conversation_id=conv_id,
    task_params=TaskParams(cookie_ids=["uuid"]),
)
```

## ⚡ 性能优化速查

| 问题 | 解决方案 |
|------|---------|
| 采集太慢 | 降低 `scroll_pause_ms`，增加 `response_timeout_sec` |
| 经常超时 | 增加 `response_timeout_sec`，增加 `max_seconds` |
| 容易被限流 | 添加 `await asyncio.sleep(2)`，减小 `max_items` |
| 内存占用高 | 使用增量同步，减小 `max_items` |
| Cookie过期 | 重新手动登录（`headless=False`, `cookie_ids=[]`） |

## 🐛 调试技巧

```python
# 1. 显示浏览器窗口
TaskParams(headless=False)

# 2. 获取原始数据
ServiceParams(need_raw_data=True)

# 3. 查看日志
# 日志位置: logs/app.log

# 4. 延长超时时间
ServiceParams(
    response_timeout_sec=30.0,
    max_seconds=1200,
)
```

## 📚 更多文档

- 完整API文档：`plugins_api_reference.md`
- 项目说明：`CLAUDE.md`
- 示例代码：`examples/`
- 迁移指南：`xiaohongshu_details_v3_migration.md`

## 🔗 链接速查

| 文档 | 路径 |
|------|------|
| 完整API参考 | `docs/plugins_api_reference.md` |
| 快速参考（本文档） | `docs/plugins_quick_reference.md` |
| 项目文档 | `CLAUDE.md` |
| 配置示例 | `config.example.json5` |
| 示例代码 | `examples/` |
| RPC客户端参数 | `client_sdk/params.py` |

---

**提示**:
- ✅ 必需参数一定要提供
- 🔄 收藏夹类插件建议使用增量同步
- ⏱️ 批量操作务必添加延迟
- 🔒 妥善保管 Cookie ID 和 master_key
