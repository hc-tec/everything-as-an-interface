### data_sync 使用指南（被动同步引擎）

本模块提供一个“被动同步 + 停止条件”引擎，用于把你每一批抓取/解析到的记录与本地快照进行对比，自动识别新增、更新和删除，并在达到一定阈值后自动停止采集。

适用于任何分页/滚动式的采集任务（如收藏列表、帖子流、评论流等）。你只需要提供“当前批次的记录”，引擎会：
- 比对并写入新增/更新
- 处理删除（软删除或物理删除）
- 依据阈值给出是否应当停止继续抓取的建议

---

### 核心组件

- `SyncConfig`：同步与停止策略配置
  - `identity_key`：记录主键字段（默认 `id`）
  - `deletion_policy`：`soft` 软删除（默认）或 `hard` 物理删除
  - `soft_delete_flag` / `soft_delete_time_key`：软删除标记与时间字段名
  - 停止条件：`stop_after_consecutive_known`、`stop_after_no_change_batches`、`max_new_items`
  - 内容指纹（全量使用）：系统统一采用指纹检测变更
    - `prefer_fingerprint`：是否优先使用指纹判定（默认 True，且引擎仅使用指纹）
    - `fingerprint_fields`：仅对这些字段计算指纹（默认 None -> 使用除 `id`、`_fingerprint` 之外的全部字段）
    - `fingerprint_key`：持久化在存储中的指纹字段名（默认 `_fingerprint`）
    - `fingerprint_algorithm`：指纹算法，`sha1` 或 `sha256`（默认 `sha1`）

- `PassiveSyncEngine`：被动同步引擎
  - `diff_and_apply(batch)`：对比当前批次并写入存储，返回 `DiffResult`
  - `process_batch(batch)`：在一次调用里完成上一步并评估停止条件，返回 `(DiffResult, StopDecision)`
  - `evaluate_stop_condition(batch)`：仅评估停止条件（通常在 `diff_and_apply` 之后立即调用）
  - `suggest_since_timestamp()`：纯指纹模式下不返回建议（始终返回 None）

- 存储接口与实现
  - `AbstractStorage`：自定义存储需实现的抽象接口
  - `InMemoryStorage`：内存版，适合测试/小规模试用
  - `MongoStorage`：MongoDB 存储（依赖 `motor`/`pymongo`）

---

### 快速开始（内存存储）

```python
import asyncio
from datetime import datetime

from src.data_sync import PassiveSyncEngine, SyncConfig, InMemoryStorage


async def main():
    storage = InMemoryStorage()
    engine = PassiveSyncEngine(
        storage=storage,
        config=SyncConfig(
            identity_key="id",
            deletion_policy="soft",
            stop_after_consecutive_known=5,
            stop_after_no_change_batches=2,
            max_new_items=100,
        ),
    )

    # 模拟批量抓取
    batch1 = [
        {"id": "a", "title": "A1"},
        {"id": "b", "title": "B1"},
    ]
    diff1, decision1 = await engine.process_batch(batch1)
    print("added:", [r["id"] for r in diff1.added])
    print("updated:", [r["id"] for r in diff1.updated])
    print("deleted:", [r["id"] for r in diff1.deleted])
    print("should_stop:", decision1.should_stop, decision1.reason)

    # 下一批：更新 a，新增 c（b 缺失将被视为删除）
    batch2 = [
        {"id": "a", "title": "A2"},
        {"id": "c", "title": "C1"},
    ]
    diff2, decision2 = await engine.process_batch(batch2)
    print("added:", [r["id"] for r in diff2.added])
    print("updated:", [r["id"] for r in diff2.updated])
    print("deleted:", [r["id"] for r in diff2.deleted])
    print("should_stop:", decision2.should_stop, decision2.reason)

asyncio.run(main())
```

---

### 与分页/滚动采集集成的推荐流程

```python
from typing import Iterable, Dict, Any


async def collect_and_sync(engine, fetch_pages) -> None:
    """fetch_pages 应返回一个异步生成器/可迭代器，按页产出记录列表。"""
    async for records in fetch_pages():
        # records: List[Mapping[str, Any]]，每条至少包含 identity_key；指纹模式不要求 updated_at
        diff, decision = await engine.process_batch(records)

        # 可基于 diff 做额外处理（日志、指标、事件）
        if decision.should_stop:
            break
```

要点：
- 若上游支持“增量参数”（如 `since`、`updated_after`），可在会话开始前调用 `engine.suggest_since_timestamp()` 获取建议的起点。
- 每处理一个批次后立即调用 `process_batch`（或先 `diff_and_apply` 再 `evaluate_stop_condition` + `update_session_counters`），以便精确更新停止状态。

---

### 记录格式与变更检测

- 必需字段：`identity_key` 对应的主键。缺失会抛出 `KeyError`。
- 指纹检测：
  - 系统统一使用内容指纹识别更新。
  - 指纹字段集合可通过 `fingerprint_fields` 指定；未指定时，排除 `id`/`_fingerprint` 等记账字段。
  - 若存储层实现了 `_fingerprint` 的读写接口，可避免加载整条记录进行对比，效率更高。
  - 若首次无历史指纹，仍会回退到浅层字典比较一次，以避免误报。

---

### 删除策略

- `soft`（默认）：不会从存储中物理删除文档，而是写入 `soft_delete_flag=True` 与 `soft_delete_time_key` 时间戳。
- `hard`：直接从存储中删除缺失记录。

根据你的业务需要选择策略：若需要保留历史并可恢复，选择软删除；若只关心现状且存储清爽，选择物理删除。

---

### MongoDB 存储示例

依赖安装（可在你的项目虚拟环境中）：

```bash
pip install motor pymongo
```

使用示例：

```python
import motor.motor_asyncio
from src.data_sync import PassiveSyncEngine, SyncConfig, MongoStorage


client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = client["mydb"]
col = db["my_collection"]

engine = PassiveSyncEngine(
    storage=MongoStorage(motor_collection=col, id_field="id"),
    config=SyncConfig(identity_key="id", deletion_policy="soft"),
)
```

---

### 自定义存储实现

实现 `AbstractStorage` 的下列方法即可接入任意数据库/文件存储：

```python
class AbstractStorage(ABC):
    async def get_by_id(self, identity: str) -> Optional[Dict[str, Any]]: ...
    async def upsert_many(self, items: Iterable[Mapping[str, Any]]) -> int: ...
    async def mark_deleted(self, identity_list: Iterable[str], *, soft_flag: str, soft_time_key: str) -> int: ...
    async def delete_many(self, identity_list: Iterable[str]) -> int: ...
    async def list_all_id_to_updated_at(self, *, id_field: str, updated_at_field: str) -> Dict[str, Optional[datetime]]: ...
    # 可选：为指纹检测提供加速（推荐实现）
    async def get_fingerprint_by_id(self, identity: str, *, fingerprint_key: str) -> Optional[str]: ...
    async def upsert_fingerprint(self, identity: str, fingerprint: str, *, fingerprint_key: str) -> None: ...
```

注意：
- `list_all_id_to_updated_at` 仅用于探测“已知 id”存在性；引擎不再依赖具体时间值。
- `upsert_many`、`delete_many`、`mark_deleted` 返回受影响的条数（整数）。

---

### 常见问题

- 没有 `updated_at` 怎么办？
  - 默认启用“内容指纹”检测更新；若存储未实现指纹接口也可工作，只是会更频繁地加载文档回退比较。

- 怎样控制“何时停止抓取”？
  - 通过 `SyncConfig` 的三个阈值灵活组合：
    - `stop_after_consecutive_known`：连续命中已知条目过多时停止
    - `stop_after_no_change_batches`：连续“无新增/更新”的批次数达到阈值时停止
    - `max_new_items`：本会话新增累计达到上限时停止

- 如何做增量抓取？
  - 会话开始前调用 `engine.suggest_since_timestamp()`，把返回值传给你的数据源筛选参数（如 `updated_after`）。

---

### 参考

- 参考测试用例：`tests/data_sync/test_engine.py` 展示了完整的新增/更新/删除与停止策略示例。


