# Webhook Payload Chunking

## 概述

Webhook Payload Chunking 是一个自动化的负载分块机制，用于解决大型数据集在 webhook 传输时超过接收服务器大小限制的问题。该功能在服务器端自动检测并分割大负载，在客户端自动重组，对应用层完全透明。

## 背景与问题

### 问题描述

在数据采集场景中，插件可能返回大量数据项（如数百条笔记、视频、收藏等）。当这些数据通过 webhook 推送时，可能出现以下问题：

```
HTTP 413 Payload Too Large
Maximum request body size 1048576 exceeded, actual body size 1179185
```

常见限制：
- **aiohttp 默认限制**: 1MB (1048576 bytes)
- **Nginx 默认限制**: 1MB (`client_max_body_size`)
- **其他 Web 服务器**: 通常 1-10MB

### 影响范围

- 数据量大的插件无法正常推送结果
- RPC 调用超时或失败
- 流式订阅中断

## 解决方案架构

### 设计原则

1. **透明性**: 应用层无需修改代码
2. **自动化**: 自动检测和处理分块
3. **可靠性**: 保持 HMAC 签名验证
4. **可配置**: 支持自定义分块大小
5. **向后兼容**: 不影响现有小负载的传输

### 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                        Plugin Result                          │
│                  (Large payload: 1.2MB)                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              WebhookDispatcher (Server)                       │
│  ┌────────────────────────────────────────────────────┐      │
│  │ _deliver_job_with_chunking()                       │      │
│  │   ├─ _chunk_payload()                              │      │
│  │   │   ├─ Size detection (> 800KB?)                 │      │
│  │   │   ├─ Split result.items array                  │      │
│  │   │   └─ Add chunk metadata                        │      │
│  │   └─ Send multiple webhooks                        │      │
│  └────────────────────────────────────────────────────┘      │
└────────────────────────┬─────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
     Chunk 0         Chunk 1       Chunk 2
    (800KB)         (800KB)       (400KB)
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│               EAIRPCClient (Client)                           │
│  ┌────────────────────────────────────────────────────┐      │
│  │ _handle_webhook()                                  │      │
│  │   ├─ Detect is_chunked flag                        │      │
│  │   ├─ Buffer chunks by event_id                     │      │
│  │   ├─ _reassemble_chunks()                          │      │
│  │   │   ├─ Check all chunks received                 │      │
│  │   │   ├─ Sort by chunk_index                       │      │
│  │   │   └─ Merge result.items arrays                 │      │
│  │   └─ Deliver complete payload                      │      │
│  └────────────────────────────────────────────────────┘      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   Complete Result                             │
│              (Reassembled, transparent)                       │
└──────────────────────────────────────────────────────────────┘
```

## 实现细节

### 服务器端 (WebhookDispatcher)

#### 1. 分块检测

```python
def _chunk_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    # 序列化测试
    test_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(test_body) <= self._max_chunk_size:
        return [payload]  # 无需分块

    # 需要分块
    logger.info("Payload size %d exceeds max chunk size %d",
                len(test_body), self._max_chunk_size)
```

#### 2. 智能分块策略

优先级：
1. **result.items 数组**: 最常见模式，按数据项分割
2. **result 直接为列表**: 按列表项分割
3. **回退方案**: 记录警告，发送原始负载

```python
result = payload.get("result", {})
if isinstance(result, dict) and "items" in result:
    return self._chunk_result_items(payload, result["items"])
elif isinstance(result, list):
    return self._chunk_result_items(payload, result)
```

#### 3. 分块大小估算

```python
# 计算基础开销（不含 items）
base_size = len(json.dumps(base_payload_copy, ensure_ascii=False).encode("utf-8"))
overhead = base_size + 200  # 分块元数据预估

# 估算平均项大小
sample_items = items[:min(10, len(items))]
sample_bytes = len(json.dumps(sample_items, ensure_ascii=False).encode("utf-8"))
avg_item_size = sample_bytes / len(sample_items)

# 计算每块项数
items_per_chunk = max(1, int((max_chunk_size - overhead) / avg_item_size))
```

#### 4. 分块元数据

每个分块添加以下字段：

```json
{
  "is_chunked": true,
  "chunk_index": 0,
  "total_chunks": 3,
  "chunk_id": "uuid-for-this-chunk",
  "event_id": "same-as-original",
  "result": {
    "items": [/* 分块数据 */]
  }
}
```

### 客户端 (EAIRPCClient)

#### 1. 分块检测与缓冲

```python
async def _handle_webhook(self, request: web.Request) -> web.Response:
    payload = json.loads(raw_body.decode("utf-8"))

    is_chunked = payload.get("is_chunked", False)
    if is_chunked:
        chunk_index = payload.get("chunk_index", 0)

        # 存储到缓冲区
        if x_eai_event_id not in self._chunk_buffers:
            self._chunk_buffers[x_eai_event_id] = {}
        self._chunk_buffers[x_eai_event_id][chunk_index] = payload
```

#### 2. 重组逻辑

```python
def _reassemble_chunks(self, event_id: str) -> Optional[Dict[str, Any]]:
    chunks = self._chunk_buffers[event_id]

    # 检查完整性
    first_chunk = next(iter(chunks.values()))
    total_chunks = first_chunk.get("total_chunks", 0)
    if len(chunks) != total_chunks:
        return None  # 还未收齐

    # 按索引排序
    sorted_chunks = [chunks[i] for i in range(total_chunks)]

    # 合并 result.items
    all_items = []
    for chunk in sorted_chunks:
        chunk_result = chunk.get("result", {})
        if isinstance(chunk_result, dict) and "items" in chunk_result:
            all_items.extend(chunk_result["items"])

    # 清理元数据
    reassembled = dict(sorted_chunks[0])
    reassembled.pop("is_chunked", None)
    reassembled.pop("chunk_index", None)
    reassembled.pop("total_chunks", None)
    reassembled["result"]["items"] = all_items

    return reassembled
```

#### 3. 去重处理

```python
# 只对完整 payload 去重，不对单独分块去重
if x_eai_event_id and not is_chunked and not self._events_seen.add_if_new(x_eai_event_id):
    return web.json_response({"ok": True, "duplicate": True})
```

## 配置说明

### 服务器配置

在 `config.example.json5` 中添加：

```json5
{
  "webhooks": {
    "concurrency": 4,                    // 并发 worker 数
    "request_timeout_sec": 100.0,        // 单个请求超时
    "max_chunk_size_bytes": 800000,      // 最大分块大小 (800KB)
    "max_retries": 5                     // 最大重试次数
  }
}
```

#### 参数调优指南

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `max_chunk_size_bytes` | 800000 | 低于目标服务器限制 20% 作为安全边界 |
| `concurrency` | 4-8 | 根据目标服务器负载能力调整 |
| `request_timeout_sec` | 100-300 | 考虑网络延迟和服务器处理时间 |

### 客户端配置

客户端无需额外配置，自动支持分块接收。

## 使用示例

### RPC 调用（自动分块）

```python
from client_sdk.rpc_client_async import EAIRPCClient
from client_sdk.params import TaskParams, ServiceParams

client = EAIRPCClient(
    base_url="http://127.0.0.1:8008",
    api_key="testkey"
)
await client.start()

# 即使返回大量数据，也会自动分块传输
result = await client.get_collection_favorite_items_from_xiaohongshu(
    collection_id="xxx",
    task_params=TaskParams(cookie_ids=["uuid"]),
    service_params=ServiceParams(max_items=500)  # 可能产生大负载
)

# result 是完整重组后的数据，应用层无感知
print(f"Received {len(result['items'])} items")

await client.stop()
```

### 日志输出示例

**服务器端日志**:
```
2025-10-17 01:30:15 - INFO - Payload size 1179185 exceeds max chunk size 800000, chunking required
2025-10-17 01:30:15 - INFO - Chunking 200 items into chunks of ~50 items each
2025-10-17 01:30:15 - INFO - Payload split into 4 chunks
2025-10-17 01:30:15 - INFO - Webhook delivered: url=http://127.0.0.1:51959/webhook status=200
2025-10-17 01:30:15 - INFO - Webhook delivered: url=http://127.0.0.1:51959/webhook status=200
2025-10-17 01:30:16 - INFO - Webhook delivered: url=http://127.0.0.1:51959/webhook status=200
2025-10-17 01:30:16 - INFO - Webhook delivered: url=http://127.0.0.1:51959/webhook status=200
```

**客户端日志**:
```
2025-10-17 01:30:15 - INFO - Received chunk 1/4 for event abc-123-def
2025-10-17 01:30:15 - INFO - Received chunk 2/4 for event abc-123-def
2025-10-17 01:30:16 - INFO - Received chunk 3/4 for event abc-123-def
2025-10-17 01:30:16 - INFO - Received chunk 4/4 for event abc-123-def
2025-10-17 01:30:16 - INFO - Reassembled 4 chunks for event abc-123-def
```

## 故障排查

### 问题 1: 仍然出现 413 错误

**原因**: `max_chunk_size_bytes` 设置过大

**解决方案**:
```json5
// 降低分块大小
"max_chunk_size_bytes": 500000  // 从 800KB 降到 500KB
```

### 问题 2: 客户端收不到完整数据

**症状**: RPC 调用超时或返回不完整数据

**排查步骤**:
1. 检查客户端日志，确认是否收到所有分块
2. 检查网络稳定性
3. 增加 RPC 超时时间：
```python
result = await client.xxx(rpc_timeout_sec=300)  # 从 60s 增加到 300s
```

### 问题 3: 分块顺序错乱

**原因**: 并发发送导致到达顺序不同

**说明**: 这是正常现象，客户端会根据 `chunk_index` 自动排序重组，无需处理。

### 问题 4: 内存占用高

**症状**: 客户端内存持续增长

**原因**: 分块缓冲区未清理（可能是接收不完整）

**解决方案**: 添加缓冲区过期清理机制（未来改进）

## 性能考虑

### 分块开销

| 场景 | 时间开销 | 说明 |
|------|----------|------|
| 小负载 (< 800KB) | ~0ms | 无分块，直接发送 |
| 2 个分块 | ~100-200ms | 序列化 + 2次网络往返 |
| 4 个分块 | ~200-400ms | 序列化 + 4次网络往返 |

### 优化建议

1. **减少数据量**: 在插件层使用 `max_items` 限制
2. **数据压缩**: 未来可考虑 gzip 压缩（需客户端支持）
3. **增量同步**: 使用 `PassiveSyncEngine` 只传输变更
4. **提高接收端限制**: 修改 aiohttp 配置：
```python
app = web.Application(client_max_size=10*1024*1024)  # 10MB
```

## 限制与注意事项

### 当前限制

1. **只支持 result.items 结构**: 其他数据结构会记录警告
2. **同步发送分块**: 未使用并发发送，可能较慢
3. **无缓冲区过期**: 未完成的分块会占用内存
4. **无分块压缩**: 未实现额外压缩

### 安全考虑

1. **HMAC 签名**: 每个分块独立签名验证
2. **事件去重**: 避免重复处理完整 payload
3. **大小限制**: 防止恶意超大负载

### 未来改进

- [ ] 并发发送分块，减少延迟
- [ ] 分块缓冲区 TTL，自动清理过期数据
- [ ] gzip 压缩支持
- [ ] 支持更多数据结构的智能分块
- [ ] 分块传输进度回调

## 相关文件

- `src/api/webhook_dispatcher.py`: 服务器端分块实现
- `client_sdk/rpc_client_async.py`: 客户端重组实现
- `src/api/server.py`: 服务器配置集成
- `config.example.json5`: 配置示例

## 参考资料

- [RFC 7231 - HTTP/1.1: 413 Payload Too Large](https://tools.ietf.org/html/rfc7231#section-6.5.11)
- [aiohttp Server Configuration](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.Application)
- [Webhook Best Practices](https://webhooks.fyi/)
