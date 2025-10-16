# 插件 API 参考文档

本文档详细说明了所有可用插件的参数、返回值和使用示例。

## 目录

- [小红书插件](#小红书插件)
  - [收藏夹简略信息](#xiaohongshu_favorites_brief)
  - [笔记详情](#xiaohongshu_details)
  - [笔记搜索](#xiaohongshu_search)
  - [收藏夹列表](#xiaohongshu_collection_list)
- [Bilibili插件](#bilibili插件)
  - [收藏夹列表](#bilibili_collection_list)
  - [收藏夹视频](#bilibili_collection_videos)
  - [视频详情](#bilibili_video_details)
- [知乎插件](#知乎插件)
  - [收藏夹列表](#zhihu_collection_list)
- [AI聊天插件](#ai聊天插件)
  - [元宝聊天](#yuanbao_chat)
- [OCR插件](#ocr插件)
  - [PaddleOCR](#paddle_ocr)
- [通用参数说明](#通用参数说明)

---

## 小红书插件

### xiaohongshu_favorites_brief

获取小红书收藏夹中的笔记简略信息，支持增量同步。

#### 插件ID
`xiaohongshu_favorites_brief`

#### 版本
v2.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `storage_data` | `str` / `list` | 否 | `"[]"` | 已存储的数据（JSON字符串或列表），用于增量同步 |
| `collection_id` | `str` | 否 | `None` | 指定收藏夹ID，为空则获取默认收藏夹 |

**TaskParams（任务参数）：**
- `cookie_ids`: Cookie ID列表（必需）
- `headless`: 是否无头模式
- `close_page_when_task_finished`: 任务完成后是否关闭页面

**ServiceParams（服务参数）：**
- `max_items`: 最大采集条数
- `scroll_pause_ms`: 滚动暂停时间（毫秒）
- `response_timeout_sec`: 网络响应超时时间（秒）

**SyncParams（同步参数）：**
- `stop_after_consecutive_known`: 连续已知项停止阈值
- `stop_after_no_change_batches`: 无变化批次停止阈值
- `max_new_items`: 最大新增项数

#### 返回值

```python
{
    "success": True,
    "plugin_id": "xiaohongshu_favorites_brief",
    "plugin_version": "2.0.0",
    "timestamp": "2025-01-15T10:30:00Z",
    "data": {
        "data": [  # 全量数据
            {
                "id": "note_id_123",
                "xsec_token": "xxx",
                "title": "笔记标题",
                "author_info": {
                    "user_id": "user_123",
                    "username": "作者名",
                    "avatar": "https://...",
                    "xsec_token": "yyy"
                },
                "statistic": {
                    "like_num": "1234",
                    "collect_num": "567",
                    "chat_num": "89"
                },
                "cover_image": "https://...",
                "raw_data": {...}  # 原始数据
            },
            // ... 更多笔记
        ],
        "count": 150,  # 总数
        "added": {  # 本次新增的数据
            "data": [...],
            "count": 10
        },
        "updated": {  # 本次更新的数据
            "data": [...],
            "count": 5
        }
    }
}
```

#### 使用示例

```python
from client_sdk.rpc_client_async import EAIRPCClient
from client_sdk.params import TaskParams, ServiceParams, SyncParams

client = EAIRPCClient(base_url="http://127.0.0.1:8008", api_key="testkey")
await client.start()

# 首次同步
result = await client.get_favorite_notes_brief_from_xhs(
    storage_data="[]",  # 空数组表示首次同步
    task_params=TaskParams(
        cookie_ids=["your-cookie-id"],
    ),
    service_params=ServiceParams(
        max_items=100,
        scroll_pause_ms=1000,
    ),
    sync_params=SyncParams(
        stop_after_consecutive_known=10,
        max_new_items=50,
    ),
)

# 增量同步（传入上次的全量数据）
result2 = await client.get_favorite_notes_brief_from_xhs(
    storage_data=result["data"]["data"],  # 传入上次的数据
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)
```

---

### xiaohongshu_details

获取单个小红书笔记的详细信息。

#### 插件ID
`xiaohongshu_details`

#### 版本
v3.0.0（重大更新：改为单笔记处理）

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `note_id` | `str` | ✅ 是 | - | 笔记ID |
| `xsec_token` | `str` | ✅ 是 | - | 笔记的xsec_token |
| `wait_time_sec` | `int` | 否 | `3` | 页面加载等待时间（秒） |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "xiaohongshu_details",
    "plugin_version": "3.0.0",
    "timestamp": "2025-01-15T10:30:00Z",
    "data": {
        "id": "note_id_123",
        "xsec_token": "xxx",
        "title": "笔记标题",
        "desc": "笔记详细描述内容...",
        "author_info": {
            "user_id": "user_123",
            "username": "作者名",
            "avatar": "https://...",
            "xsec_token": "yyy"
        },
        "tags": ["标签1", "标签2"],
        "date": "2025-01-01",
        "ip_zh": "北京",
        "comment_num": "123",
        "statistic": {
            "like_num": "5678",
            "collect_num": "1234",
            "chat_num": "234"
        },
        "images": [
            "https://image1.jpg",
            "https://image2.jpg"
        ],
        "video": {
            "duration_sec": 60,
            "src": "https://video.mp4",
            "id": "video_123"
        },
        "timestamp": "1640000000000",
        "raw_data": {...}
    }
}
```

#### 使用示例

```python
# 获取单个笔记详情
result = await client.get_note_detail_from_xhs(
    note_id="65a1b2c3d4e5f6g7h8i9j0k",
    xsec_token="XYZ123ABC456",
    wait_time_sec=3,
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)

if result["success"]:
    detail = result["data"]
    print(f"标题: {detail['title']}")
    print(f"描述: {detail['desc']}")
    print(f"点赞: {detail['statistic']['like_num']}")
```

---

### xiaohongshu_search

搜索小红书笔记。

#### 插件ID
`xiaohongshu_search`

#### 版本
v2.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `search_words` | `str` | ✅ 是 | - | 搜索关键词 |

**ServiceParams：**
- `max_items`: 最大搜索结果数
- `scroll_pause_ms`: 滚动暂停时间

#### 返回值

```python
{
    "success": True,
    "plugin_id": "xiaohongshu_search",
    "plugin_version": "2.0.0",
    "data": [
        {
            "id": "note_id_123",
            "xsec_token": "xxx",
            "title": "搜索结果标题",
            "author_info": {...},
            "statistic": {...},
            "cover_image": "https://...",
            "raw_data": {...}
        },
        // ... 更多结果
    ]
}
```

#### 使用示例

```python
result = await client.search_notes_from_xhs(
    keywords=["咖啡馆", "探店"],
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
    service_params=ServiceParams(max_items=50),
)
```

---

### xiaohongshu_collection_list

获取小红书收藏夹列表。

#### 插件ID
`xiaohongshu_collection_list`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `user_id` | `str` | 否 | `None` | 用户ID，为空则获取当前登录用户 |

#### 返回值

```python
{
    "success": True,
    "data": [
        {
            "id": "collection_123",
            "title": "收藏夹名称",
            "cover": "https://...",
            "description": "收藏夹描述",
            "item_count": 150,
            "is_default": True,
            "created_time": 1640000000,
            "updated_time": 1640100000,
            "raw_data": {...}
        },
        // ... 更多收藏夹
    ]
}
```

---

## Bilibili插件

### bilibili_collection_list

获取B站收藏夹列表。

#### 插件ID
`bilibili_collection_list`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `user_id` | `str` | 否 | `None` | 用户ID，为空则获取当前登录用户 |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "bilibili_collection_list",
    "plugin_version": "1.0.0",
    "data": [
        {
            "id": "12345678",
            "title": "默认收藏夹",
            "description": "收藏夹简介",
            "cover": "https://...",
            "link": "https://...",
            "item_count": 1332,
            "is_default": True,
            "creator": {
                "user_id": "475310928",
                "username": "用户名",
                "avatar": "https://...",
                "gender": None,
                "is_following": None,
                "is_followed": None,
                "user_type": None
            },
            "created_time": 1570167288,
            "updated_time": 1663001255,
            "raw_data": {...}
        },
        // ... 更多收藏夹
    ]
}
```

#### 使用示例

```python
result = await client.get_collection_list_from_bilibili(
    user_id=None,  # 获取当前登录用户的收藏夹
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)
```

---

### bilibili_collection_videos

获取B站收藏夹中的视频列表，支持增量同步。

#### 插件ID
`bilibili_collection_videos`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `collection_id` | `str` | ✅ 是 | - | 收藏夹ID |
| `storage_data` | `str` / `list` | 否 | `[]` | 已存储的数据，用于增量同步 |
| `user_id` | `str` | 否 | `None` | 用户ID，为空则获取当前登录用户 |
| `total_page` | `int` | 否 | `None` | 总页数（自动检测） |
| `fingerprint_fields` | `list[str]` | 否 | `None` | 指纹字段列表 |

**SyncParams：**同小红书收藏夹

#### 返回值

```python
{
    "success": True,
    "plugin_id": "bilibili_collection_videos",
    "plugin_version": "1.0.0",
    "data": {
        "data": [  # 全量数据
            {
                "id": "BV1xx411c7XZ",
                "title": "视频标题",
                "cover": "https://...",
                "link": "https://...",
                "duration": "10:30",
                "author_info": {
                    "user_id": "123456",
                    "username": "UP主名",
                    "avatar": "https://..."
                },
                "statistic": {
                    "view_count": "100万",
                    "like_count": "5万",
                    "coin_count": "2万",
                    "favorite_count": "1万"
                },
                "publish_time": 1640000000,
                "collected_time": 1640100000,
                "raw_data": {...}
            },
            // ... 更多视频
        ],
        "count": 200,
        "added": {
            "data": [...],
            "count": 10
        },
        "updated": {
            "data": [...],
            "count": 5
        }
    }
}
```

#### 使用示例

```python
result = await client.get_collection_list_videos_from_bilibili(
    collection_id="737546928",
    user_id=None,
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
    service_params=ServiceParams(max_items=500),
)
```

---

### bilibili_video_details

获取B站视频详情。

#### 插件ID
`bilibili_video_details`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `bvid` | `str` | ✅ 是 | - | 视频BV号 |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "bilibili_video_details",
    "data": {
        "bvid": "BV1xx411c7XZ",
        "aid": "123456789",
        "title": "视频标题",
        "desc": "视频简介",
        "cover": "https://...",
        "duration": 630,  # 秒
        "author_info": {
            "user_id": "123456",
            "username": "UP主名",
            "avatar": "https://..."
        },
        "statistic": {
            "view": 1000000,
            "danmaku": 5000,
            "reply": 2000,
            "favorite": 10000,
            "coin": 20000,
            "share": 3000,
            "like": 50000
        },
        "tags": ["标签1", "标签2"],
        "publish_time": 1640000000,
        "cid": 987654321,
        "pages": [
            {
                "page": 1,
                "part": "P1",
                "duration": 630,
                "dimension": {
                    "width": 1920,
                    "height": 1080
                }
            }
        ],
        "raw_data": {...}
    }
}
```

#### 使用示例

```python
result = await client.get_video_details_from_bilibili(
    bvid="BV1xx411c7XZ",
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)
```

---

## 知乎插件

### zhihu_collection_list

获取知乎收藏夹列表。

#### 插件ID
`zhihu_collection_list`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `user_id` | `str` | 否 | `None` | 用户ID（URL中的ID），为空则获取当前登录用户 |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "zhihu_collection_list",
    "data": [
        {
            "id": "collection_123",
            "title": "收藏夹标题",
            "description": "收藏夹描述",
            "cover": "https://...",
            "item_count": 100,
            "follower_count": 50,
            "is_public": True,
            "creator": {
                "user_id": "user_123",
                "username": "用户名",
                "avatar": "https://..."
            },
            "created_time": 1640000000,
            "updated_time": 1640100000,
            "raw_data": {...}
        },
        // ... 更多收藏夹
    ]
}
```

#### 使用示例

```python
result = await client.get_collection_list_from_zhihu(
    user_id=None,
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)
```

---

## AI聊天插件

### yuanbao_chat

与腾讯元宝AI进行对话。

#### 插件ID
`yuanbao_chat`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `ask_question` | `str` | ✅ 是 | - | 提问内容 |
| `conversation_id` | `str` | 否 | `None` | 会话ID，为空则创建新会话 |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "yuanbao_chat",
    "plugin_version": "1.0.0",
    "data": [
        {
            "conversation_id": "conv_123",
            "question": "你好，请介绍一下自己",
            "answer": "你好！我是腾讯元宝...",
            "last_model_message": "你好！我是腾讯元宝...",
            "timestamp": 1640000000,
            "raw_data": {...}
        }
    ]
}
```

#### 使用示例

```python
# 新会话
result = await client.chat_with_yuanbao(
    ask_question="你好，我是小星星",
    conversation_id=None,
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)

# 继续会话
conv_id = result["data"][0]["conversation_id"]
result2 = await client.chat_with_yuanbao(
    ask_question="请帮我写一首诗",
    conversation_id=conv_id,
    task_params=TaskParams(cookie_ids=["your-cookie-id"]),
)
```

---

## OCR插件

### paddle_ocr

使用PaddleOCR进行图像文字识别。

#### 插件ID
`paddle_ocr`

#### 版本
v1.0.0

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `image_path_abs_path` | `str` | ✅ 是 | - | 图片绝对路径 |
| `lang` | `str` | 否 | `"ch"` | 语言：`ch`(中文), `en`(英文), `ch_en`(中英文) |
| `include_text` | `bool` | 否 | `True` | 是否包含识别文本 |
| `need_merge_lines` | `bool` | 否 | `True` | 是否合并多行文本 |
| `include_boxes` | `bool` | 否 | `False` | 是否包含文本框坐标 |
| `include_confidence` | `bool` | 否 | `True` | 是否包含置信度 |
| `include_layout` | `bool` | 否 | `False` | 是否包含布局分析 |
| `include_table` | `bool` | 否 | `False` | 是否包含表格识别 |
| `include_raw_image` | `bool` | 否 | `True` | 是否包含原始图片信息 |

#### 返回值

```python
{
    "success": True,
    "plugin_id": "paddle_ocr",
    "data": {
        "text": "识别出的完整文本内容",
        "lines": [
            {
                "text": "第一行文本",
                "confidence": 0.98,
                "box": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            },
            {
                "text": "第二行文本",
                "confidence": 0.95,
                "box": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            }
        ],
        "image_info": {
            "path": "/path/to/image.jpg",
            "width": 1920,
            "height": 1080,
            "format": "JPEG"
        }
    }
}
```

#### 使用示例

```python
result = await client.call_paddle_ocr(
    image_path_abs_path="D:/images/document.jpg",
    lang="ch",
    include_text=True,
    need_merge_lines=True,
    include_confidence=True,
    task_params=TaskParams(),
)

if result["success"]:
    print(f"识别文本: {result['data']['text']}")
```

---

## 通用参数说明

所有插件都支持以下通用参数类别：

### TaskParams（任务参数）

控制浏览器和任务的基本设置。

```python
from client_sdk.params import TaskParams

task_params = TaskParams(
    headless=True,  # 是否无头模式（不显示浏览器窗口）
    cookie_ids=["uuid-1", "uuid-2"],  # Cookie ID列表
    viewport={"width": 1280, "height": 800},  # 浏览器视口大小
    user_agent="Mozilla/5.0...",  # 自定义User-Agent
    extra_http_headers={"X-Custom": "value"},  # 额外HTTP头
    close_page_when_task_finished=False,  # 任务完成后是否关闭页面
)
```

### ServiceParams（服务参数）

控制数据收集行为。

```python
from client_sdk.params import ServiceParams

service_params = ServiceParams(
    response_timeout_sec=5.0,  # 网络响应超时（秒）
    delay_ms=500,  # 请求延迟（毫秒）
    scroll_pause_ms=800,  # 滚动暂停时间（毫秒）
    max_idle_rounds=2,  # 最大空闲轮次
    max_items=10000,  # 最大采集条数
    max_seconds=600,  # 最大执行时间（秒）
    auto_scroll=True,  # 是否自动滚动
    scroll_mode="default",  # 滚动模式：default/selector/pager
    scroll_selector=None,  # 自定义滚动元素选择器
    max_pages=None,  # 最大页数
    pager_selector=None,  # 分页选择器
    need_raw_data=False,  # 是否需要原始数据
)
```

### SyncParams（同步参数）

控制增量同步行为。

```python
from client_sdk.params import SyncParams

sync_params = SyncParams(
    identity_key="id",  # 唯一标识字段
    deletion_policy="soft",  # 删除策略：soft/hard
    soft_delete_flag="deleted",  # 软删除标记字段
    soft_delete_time_key="deleted_at",  # 软删除时间字段
    stop_after_consecutive_known=10,  # 连续已知项停止阈值
    stop_after_no_change_batches=3,  # 无变化批次停止阈值
    max_new_items=100,  # 最大新增项数
    fingerprint_fields=["title", "content"],  # 指纹字段
    fingerprint_key="_fingerprint",  # 指纹存储字段
    fingerprint_algorithm="sha1",  # 指纹算法：sha1/sha256
)
```

---

## 通用返回格式

所有插件的返回值都遵循统一格式：

### 成功响应

```python
{
    "success": True,
    "plugin_id": "插件ID",
    "plugin_version": "版本号",
    "timestamp": "ISO8601时间戳",
    "data": {
        # 具体数据，因插件而异
    }
}
```

### 失败响应

```python
{
    "success": False,
    "plugin_id": "插件ID",
    "plugin_version": "版本号",
    "timestamp": "ISO8601时间戳",
    "error": "错误信息描述"
}
```

---

## Cookie 管理

### 获取 Cookie ID

首次使用插件时，需要手动登录以保存 Cookie：

```python
# 设置 headless=False 以显示浏览器窗口
result = await client.get_favorite_notes_brief_from_xhs(
    storage_data="[]",
    task_params=TaskParams(
        headless=False,  # 显示浏览器
        cookie_ids=[],  # 不传入cookie，会触发手动登录
    ),
)
```

登录成功后，在日志中可以看到 Cookie ID：
```
INFO: Cookie saved with ID: 819969a2-9e59-46f5-b0ca-df2116d9c2a0
```

后续调用时使用此 ID：
```python
task_params=TaskParams(cookie_ids=["819969a2-9e59-46f5-b0ca-df2116d9c2a0"])
```

### Cookie 存储位置

Cookie 使用对称加密存储在：
```
accounts/cookies.enc
```

加密密钥在 `config.example.json5` 中配置：
```json5
{
  "app": {
    "master_key": "your-master-key-here"
  }
}
```

⚠️ **重要**：请妥善保管 `master_key`，不要提交到版本控制系统！

---

## 错误处理示例

```python
try:
    result = await client.get_note_detail_from_xhs(
        note_id="xxx",
        xsec_token="yyy",
        task_params=TaskParams(cookie_ids=["your-cookie-id"]),
    )

    if result["success"]:
        data = result["data"]
        print(f"成功: {data['title']}")
    else:
        print(f"失败: {result['error']}")

except TimeoutError:
    print("RPC调用超时")
except Exception as e:
    print(f"异常: {e}")
```

---

## 性能优化建议

1. **批量操作时添加延迟**
   ```python
   for item in items:
       result = await client.get_note_detail_from_xhs(...)
       await asyncio.sleep(2)  # 避免被限流
   ```

2. **使用增量同步**
   ```python
   # 传入上次的全量数据，只获取新增和更新
   result = await client.get_favorite_notes_brief_from_xhs(
       storage_data=previous_data,
       sync_params=SyncParams(
           stop_after_consecutive_known=10,
       ),
   )
   ```

3. **设置合理的超时**
   ```python
   service_params = ServiceParams(
       response_timeout_sec=10.0,  # 网络慢时增加超时
       max_seconds=300,  # 限制总执行时间
   )
   ```

4. **使用 headless 模式**
   ```python
   # 生产环境使用无头模式，提升性能
   task_params = TaskParams(headless=True)
   ```

---

## 常见问题

### Q: Cookie 过期怎么办？
A: 重新运行一次手动登录流程（`headless=False`, `cookie_ids=[]`）

### Q: 如何调试插件？
A:
1. 设置 `headless=False` 查看浏览器行为
2. 查看日志文件 `logs/app.log`
3. 使用 `need_raw_data=True` 获取原始数据

### Q: 数据采集速度太慢？
A: 调整参数：
- 降低 `scroll_pause_ms`
- 增加 `response_timeout_sec`
- 减少 `delay_ms`

### Q: 如何避免被限流/封号？
A:
- 添加随机延迟
- 不要设置过大的 `max_items`
- 使用增量同步而非全量采集
- 避免频繁请求

---

## 更新日志

- **2025-01-15**: 小红书详情插件升级至 v3.0（单笔记处理）
- **2025-01-15**: 添加网络超时参数支持
- **2024-12**: 初始版本

---

## 技术支持

如有问题，请查看：
- 项目文档：`CLAUDE.md`
- 示例代码：`examples/`
- GitHub Issues: [项目地址]

