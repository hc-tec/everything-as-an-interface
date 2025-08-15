from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence
import hashlib
import json


@dataclass
class SyncConfig:
    """用于被动数据同步和停止条件的配置。

    属性：
        identity_key: 用于唯一标识记录的字段名。
        deletion_policy: 'soft' 表示标记删除，'hard' 表示物理删除文档。
        soft_delete_flag: 用于标记软删除文档的字段名。
        soft_delete_time_key: 用于存储软删除时间戳的字段名。
        stop_after_consecutive_known: 当一个批次包含如此多连续的已知项时停止同步。假设设置 stop_after_consecutive_known = 5，
            那么当连续 5 条数据都是已经同步过的记录（没有发生任何变化）时，系统会停止进一步的同步，因为认为数据已经同步完成，不再需要继续抓取。
        stop_after_no_change_batches: 在没有新增或更新的批次后停止同步的批次数量。也就是说，数据抓取了一段时间后，
            如果连续几个批次都没有发现任何变化，可能说明数据已经同步完毕，或者数据源没有更多更新，于是自动停止抓取。
        max_new_items: 当本次会话中收集到的新项达到此限制时停止同步。

    Configuration for passive data synchronization and stop conditions.

    Attributes:
        identity_key: Field name used to uniquely identify a record.
        deletion_policy: 'soft' to mark deletions, 'hard' to remove documents.
        soft_delete_flag: Field name used to mark soft-deleted documents.
        soft_delete_time_key: Field name used to store deletion timestamp on soft delete.
        stop_after_consecutive_known: Stop when a batch contains this many consecutive already-known items.
        stop_after_no_change_batches: Stop after this many batches without additions or updates.
        max_new_items: Stop when new items collected in this session reach this limit.
    """

    identity_key: str = "id"
    deletion_policy: str = "soft"
    soft_delete_flag: str = "deleted"
    soft_delete_time_key: str = "deleted_at"
    stop_after_consecutive_known: Optional[int] = None
    stop_after_no_change_batches: Optional[int] = None
    max_new_items: Optional[int] = None
    # Fingerprint-based update detection (for sources without reliable updated_at)
    fingerprint_fields: Optional[Sequence[str]] = None  # None -> use all fields except bookkeeping keys
    fingerprint_key: str = "_fingerprint"
    fingerprint_algorithm: str = "sha1"  # sha1|sha256

class DiffResult:
    """Result of comparing current dataset with the stored snapshot."""

    added: List[Dict[str, Any]] = field(default_factory=list)
    updated: List[Dict[str, Any]] = field(default_factory=list)
    deleted: List[Dict[str, Any]] = field(default_factory=list)

    def __init__(self, added: List[Dict[str, Any]],
                 updated: List[Dict[str, Any]],
                 deleted: List[Dict[str, Any]]) -> None:
        self.added = added
        self.updated = updated
        self.deleted = deleted

    def stats(self) -> Mapping[str, int]:  # pragma: no cover - trivial
        return {
            "added": len(self.added),
            "updated": len(self.updated),
            "deleted": len(self.deleted),
        }


@dataclass
class StopState:
    """In-memory counters for stop condition evaluation across batches."""

    consecutive_known_items: int = 0
    consecutive_no_change_batches: int = 0
    total_new_items_in_session: int = 0


def get_record_identity(item: Mapping[str, Any], *, identity_key: str) -> str:
    value = item.get(identity_key)
    if value is None:
        raise KeyError(f"Missing identity field: {identity_key}")
    return str(value)


def select_comparable_fields(item: Mapping[str, Any], *, exclude: Sequence[str]) -> Dict[str, Any]:
    """Return a shallow copy excluding fields used for bookkeeping.

    This is used to detect changes beyond the identity and timestamp fields.
    """
    result: Dict[str, Any] = {}
    for k, v in item.items():
        if k in exclude:
            continue
        result[k] = v
    return result


def compute_fingerprint(
    item: Mapping[str, Any],
    *,
    fields: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    algorithm: str = "sha1",
) -> str:
    """Compute a stable content fingerprint for update detection.

    - If `fields` is provided, only include these keys.
    - Otherwise, include all keys except those in `exclude`.
    - Serialize with sorted keys to ensure determinism, then hash.
    """
    if fields is not None:
        subset: Dict[str, Any] = {k: item.get(k) for k in fields}
    else:
        subset = select_comparable_fields(item, exclude=exclude or [])
    try:
        payload = json.dumps(subset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        # Fallback: convert un-serializable objects to strings
        def _coerce(v: Any) -> Any:
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v
            if isinstance(v, (list, tuple)):
                return [_coerce(x) for x in v]
            if isinstance(v, dict):
                return {str(k): _coerce(val) for k, val in v.items()}
            return str(v)

        if fields is not None:
            subset = {k: _coerce(item.get(k)) for k in fields}
        else:
            subset = {k: _coerce(v) for k, v in subset.items()}
        payload = json.dumps(subset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    if algorithm == "sha256":
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    # default sha1
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


