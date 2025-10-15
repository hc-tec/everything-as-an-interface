# 小红书笔记详情插件 v3.0 迁移指南

## 概述

小红书笔记详情插件（`xiaohongshu_details`）已从 v2.0 升级到 v3.0，主要变更是**从批量处理改为单笔记处理**，简化了接口调用逻辑。

## 主要变更

### v2.0（旧版本）

- **批量处理**：一次接受多个笔记的简略信息，循环获取所有详情
- **复杂的参数结构**：需要传递包含 `count` 和 `data` 数组的 JSON 字符串
- **批量结果返回**：返回成功和失败的列表

**旧版本参数：**
```python
{
    "brief_data": json.dumps({
        "count": 10,
        "data": [
            {"id": "xxx1", "xsec_token": "yyy1"},
            {"id": "xxx2", "xsec_token": "yyy2"},
            # ... 更多笔记
        ]
    }),
    "wait_time_sec": 10
}
```

**旧版本返回：**
```python
{
    "success": True,
    "data": {
        "data": [...],  # 成功获取的详情列表
        "count": 8,
        "failed_notes": {
            "data": [...],  # 失败的笔记列表
            "count": 2
        }
    }
}
```

### v3.0（新版本）

- **单笔记处理**：一次只处理一个笔记的详情
- **简洁的参数结构**：直接传递 `note_id` 和 `xsec_token`
- **单一结果返回**：直接返回笔记详情对象

**新版本参数：**
```python
{
    "note_id": "xxx",
    "xsec_token": "yyy",
    "wait_time_sec": 3  # 默认值从10秒降为3秒
}
```

**新版本返回：**
```python
{
    "success": True,
    "data": {
        "id": "xxx",
        "title": "笔记���题",
        "desc": "笔记描述",
        "author_info": {...},
        "statistic": {...},
        # ... 其他详情字段
    }
}
```

## 迁移步骤

### 1. 更新调用代码

**旧代码（v2.0）：**
```python
# 批量获取详情
brief_data = json.dumps({
    "count": len(notes),
    "data": [
        {"id": note["id"], "xsec_token": note["xsec_token"]}
        for note in notes
    ]
})

result = await client.get_notes_details_from_xhs(
    brief_data=brief_data,
    wait_time_sec=10,
    task_params=TaskParams(cookie_ids=["uuid"]),
)

# 处理批量结果
if result["success"]:
    details = result["data"]["data"]
    failed = result["data"]["failed_notes"]["data"]
```

**新代码（v3.0）：**
```python
# 单个获取详情（需要自己实现循环）
for note in notes:
    result = await client.get_note_detail_from_xhs(
        note_id=note["id"],
        xsec_token=note["xsec_token"],
        wait_time_sec=3,
        task_params=TaskParams(cookie_ids=["uuid"]),
    )

    # 处理单个结果
    if result["success"]:
        detail = result["data"]
        # 处理详情...
    else:
        # 处理失败...

    # 添加延迟避免请求过快
    await asyncio.sleep(2)
```

### 2. 更新 RPC 客户端方法名

- **旧方法名**：`get_notes_details_from_xhs()` （复数）
- **新方法名**：`get_note_detail_from_xhs()` （单数）

### 3. 更新参数传递方式

**参数对比表：**

| 参数名 | v2.0 | v3.0 | 说明 |
|--------|------|------|------|
| `brief_data` | ✅ 必需 | ❌ 移除 | JSON 字符串，包含多个笔记信息 |
| `note_id` | ❌ 不存在 | ✅ 必需 | 单个笔记的 ID |
| `xsec_token` | ❌ 不存在 | ✅ 必需 | 单个笔记的 xsec_token |
| `wait_time_sec` | 10（默认） | 3（默认） | 页面加载等待时间 |

## 优势与劣势

### v3.0 优势

1. **更简单的接口**：参数结构清晰，易于理解
2. **更好的错误处理**：单个笔记失败不影响其他笔记
3. **更灵活的控制**：可以自定义每个笔记的处理逻辑（如延迟、重试等）
4. **更快的响应**：单个笔记获取完成即可立即处理，无需等待全部完成
5. **更低的超时风险**：批量处理时容易超时，单个处理更可控

### v3.0 劣势

1. **需要手动循环**：调用方需要自己实现循环逻辑
2. **可能更多的请求**：每个笔记都是独立的 RPC 调用
3. **需要手动管理失败**：调用方需要自己记录失败的笔记

## 最佳实践

### 1. 批量获取时添加延迟

```python
for i, note in enumerate(notes):
    print(f"正在获取第 {i+1}/{len(notes)} 个笔记详情...")

    result = await client.get_note_detail_from_xhs(
        note_id=note["id"],
        xsec_token=note["xsec_token"],
        task_params=TaskParams(cookie_ids=["uuid"]),
    )

    # 处理结果...

    # 添加延迟避免被限流
    if i < len(notes) - 1:  # 最后一个不需要延迟
        await asyncio.sleep(2)
```

### 2. 实现重试机制

```python
import asyncio
from typing import Optional

async def get_note_detail_with_retry(
    client: EAIRPCClient,
    note_id: str,
    xsec_token: str,
    max_retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """带重试机制的笔记详情获取"""
    for attempt in range(max_retries):
        try:
            result = await client.get_note_detail_from_xhs(
                note_id=note_id,
                xsec_token=xsec_token,
                task_params=TaskParams(cookie_ids=["uuid"]),
            )

            if result.get("success"):
                return result["data"]
            else:
                print(f"尝试 {attempt + 1} 失败: {result.get('error')}")
        except Exception as e:
            print(f"尝试 {attempt + 1} 异常: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(5)  # 重试前等待

    return None  # 所有重试都失败
```

### 3. 批量处理时记录进度和失败

```python
import json

async def batch_get_note_details(
    client: EAIRPCClient,
    notes: List[Dict[str, str]],
    output_file: str = "note_details.json",
):
    """批量获取笔记详情并保存"""
    success_count = 0
    failed_notes = []
    details = []

    for i, note in enumerate(notes):
        print(f"进度: {i+1}/{len(notes)}")

        result = await client.get_note_detail_from_xhs(
            note_id=note["id"],
            xsec_token=note["xsec_token"],
            task_params=TaskParams(cookie_ids=["uuid"]),
        )

        if result.get("success"):
            details.append(result["data"])
            success_count += 1
        else:
            failed_notes.append({
                "id": note["id"],
                "xsec_token": note["xsec_token"],
                "error": result.get("error")
            })

        # 定期保存进度
        if (i + 1) % 10 == 0:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "details": details,
                    "failed": failed_notes,
                    "progress": f"{i+1}/{len(notes)}"
                }, f, ensure_ascii=False, indent=2)

        await asyncio.sleep(2)

    # 最终保存
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "details": details,
            "failed": failed_notes,
            "success_count": success_count,
            "total_count": len(notes)
        }, f, ensure_ascii=False, indent=2)

    print(f"\n完成！成功: {success_count}, 失败: {len(failed_notes)}")
    return details, failed_notes
```

## 完整示例

参考文件：`examples/xiaohongshu_single_note_detail_example.py`

## 常见问题

### Q1: 为什么改为单笔记处理？

**A:** 主要原因：
1. **更好的错误隔离**：单个笔记失败不会影响其他笔记
2. **更灵活的控制**：可以根据需要自定义每个笔记的处理策略
3. **降低超时风险**：批量处理时容易因��总时间过长而超时
4. **符合 RESTful 设计**：单一资源单一请求

### Q2: 如何实现原来的批量功能？

**A:** 调用方需要自己实现循环逻辑，参考"最佳实践"中的批量处理示例。

### Q3: wait_time_sec 为什么从 10 秒降为 3 秒？

**A:** 单个笔记处理时，3 秒通常足够页面加载。如果遇到加载慢的情况，可以手动增加此参数。

### Q4: 如何处理失败的笔记？

**A:** v3.0 中，调用方需要自己记录失败的笔记。推荐使用上面"最佳实践"中的批量处理示例，它会自动记录失败的笔记和错误信息。

## 技术细节

### 移除的代码

1. **循环逻辑**：`navigate_to_note_explore_page` 回调
2. **批量停止条件**：`stop_to_note_explore_page_when_all_collected` 方法
3. **失败记录**：`on_items_collected` 回调和 `_access_failed_notes` 列表
4. **复杂的参数解析**：`brief_data` JSON 解析逻辑

### 简化的流程

```
旧流程（v2.0）：
输入 brief_data -> 解析 JSON -> 循环所有笔记 -> 每次导航 -> 收集详情 -> 汇总结果

新流程（v3.0）：
输入 note_id + xsec_token -> 导航到笔记页 -> 收集详情 -> 返回结果
```

## 版本兼容性

- **插件版本**：从 v2.0.0 升级到 v3.0.0
- **API 版本**：不兼容，需要修改调用代码
- **数据模型**：`NoteDetailsItem` 保持不变，完全兼容

## 联系与反馈

如有问题或建议，请提交 Issue 或查看项目文档。
