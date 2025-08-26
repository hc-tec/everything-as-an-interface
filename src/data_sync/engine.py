from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from src.common.plugin import StopDecision

from .models import (
    DiffResult,
    SyncParams,
    StopState,
    get_record_identity,
    select_comparable_fields,
    compute_fingerprint,
)
from .storage import AbstractStorage
from ..utils.params_helper import ParamsHelper


class PassiveSyncEngine:
    """Passive sync & diff engine.

    This engine exposes two main entrypoints:
      1) diff_and_apply(current_batch):
         - Compare incoming records with stored snapshot and apply delta
           (insert/update/delete) based on SyncParams.
         - Return DiffResult for the given batch.
      2) evaluate_stop_condition(current_batch):
         - Update internal StopState counters and determine whether a caller
           should stop further collection based on set_paramsd thresholds.

    The engine is designed to be called repeatedly with batches of freshly
    collected records (already parsed). It does not perform crawling itself.
    """

    def __init__(self, *, storage: AbstractStorage, params: Optional[SyncParams] = None) -> None:
        """初始化被动同步引擎。
        
        Args:
            storage: 存储实例
            params: 同步配置
        """
        self.storage = storage
        self.params = params or SyncParams()
        self._stop_state = StopState()

    def parse_params(self, params: Dict[str, Any]):
        self.params = ParamsHelper.build_params(SyncParams, params)

    async def diff_and_apply(self, current_records: Iterable[Mapping[str, Any]]) -> DiffResult:
        """比较传入数据与快照，应用变更并返回差异结果。
        
        Args:
            current_records: 传入的数据记录序列
            
        Returns:
            差异结果
        """
        id_key = self.params.identity_key

        incoming_by_id = self._index_incoming_records(current_records, id_key=id_key)
        snapshot_index = await self._get_snapshot_index(id_key=id_key)

        added, updated = await self._detect_additions_and_updates(
            incoming_by_id=incoming_by_id, snapshot_index=snapshot_index, id_key=id_key
        )

        missing_ids = self._detect_missing_ids(
            incoming_ids=set(incoming_by_id.keys()), snapshot_ids=set(snapshot_index.keys())
        )

        deleted = await self._apply_changes(added=added, updated=updated, missing_ids=missing_ids, id_key=id_key)

        return DiffResult(added=added, updated=updated, deleted=deleted)

    def _index_incoming_records(
        self, current_records: Iterable[Mapping[str, Any]], *, id_key: str
    ) -> Dict[str, Dict[str, Any]]:
        """为传入记录建立索引。
        
        Args:
            current_records: 传入的数据记录序列
            id_key: 身份标识键
            
        Returns:
            以身份标识为键的记录字典
        """
        """Build id -> record index for incoming batch."""
        incoming_by_id: Dict[str, Dict[str, Any]] = {}
        for rec in current_records:
            identity = get_record_identity(rec, identity_key=id_key)
            incoming_by_id[identity] = dict(rec)
        return incoming_by_id

    async def _get_snapshot_index(self, *, id_key: str) -> Dict[str, Any]:
        """获取快照索引。
        
        Args:
            id_key: 身份标识键
            
        Returns:
            以身份标识为键的快照记录字典
        """
        """Fetch snapshot mapping id -> placeholder value, using list_all_ids.

        We only need presence for additions/deletions; updates rely on fingerprints per-id.
        """
        try:
            ids = await self.storage.list_all_ids(id_field=id_key)
        except Exception:
            ids = []
        return {rid: True for rid in ids}

    async def _detect_additions_and_updates(
        self,
        *,
        incoming_by_id: Dict[str, Dict[str, Any]],
        snapshot_index: Mapping[str, Any],
        id_key: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """检测新增和更新的记录。
        
        Args:
            incoming_by_id: 传入记录索引
            snapshot_index: 快照记录索引
            id_key: 身份标识键
            
        Returns:
            新增记录列表和更新记录列表的元组
        """
        added: List[Dict[str, Any]] = []
        updated: List[Dict[str, Any]] = []
        for identity, rec in incoming_by_id.items():
            exists = identity in snapshot_index
            if not exists:
                added.append(rec)
                continue

            if await self._updated_by_fingerprint(identity=identity, rec=rec, id_key=id_key):
                updated.append(rec)
        return added, updated

    def _detect_missing_ids(self, *, incoming_ids: set[str], snapshot_ids: set[str]) -> List[str]:
        """检测缺失的记录ID。
        
        Args:
            incoming_ids: 传入记录ID集合
            snapshot_ids: 快照记录ID集合
            
        Returns:
            缺失记录ID列表
        """
        return [rid for rid in snapshot_ids if rid not in incoming_ids]

    async def _apply_changes(
        self,
        *,
        added: List[Dict[str, Any]],
        updated: List[Dict[str, Any]],
        missing_ids: List[str],
        id_key: str,
    ) -> List[Dict[str, Any]]:
        """应用变更到存储。
        
        Args:
            added: 新增记录列表
            updated: 更新记录列表
            missing_ids: 缺失记录ID列表
            id_key: 身份标识键
            
        Returns:
            删除记录列表
        """
        deleted: List[Dict[str, Any]] = []
        if added:
            await self.storage.upsert_many(added)
        if updated:
            await self.storage.upsert_many(updated)

        # 目前只是一批次的数据到来，不应该进行删除
        # if missing_ids:
        #     if self.params.deletion_policy == "soft":
        #         await self.storage.mark_deleted(
        #             missing_ids,
        #             soft_flag=self.params.soft_delete_flag,
        #             soft_time_key=self.params.soft_delete_time_key,
        #         )
        #     else:
        #         await self.storage.delete_many(missing_ids)
        #     for rid in missing_ids:
        #         deleted.append({id_key: rid})
        return deleted

    async def _updated_by_fingerprint(
        self,
        *,
        identity: str,
        rec: Mapping[str, Any],
        id_key: str,
    ) -> bool:
        """通过指纹比较判断记录是否已更新。
        
        Args:
            identity: 记录身份标识
            rec: 传入记录
            id_key: 身份标识键
            
        Returns:
            是否已更新的布尔值
        """

        exclude_keys = [id_key, self.params.fingerprint_key]

        prev_fp = await self.storage.get_fingerprint_by_id(
            identity, fingerprint_key=self.params.fingerprint_key
        )
        if prev_fp is None:
            # 重新计算 fingerprint
            prev_fp = compute_fingerprint(
                await self.storage.get_by_id(identity),
                fields=self.params.fingerprint_fields,
                exclude=self.params.fingerprint_fields is None and exclude_keys or None,
                algorithm=self.params.fingerprint_algorithm,
            )

        curr_fp = compute_fingerprint(
            rec,
            fields=self.params.fingerprint_fields,
            exclude=self.params.fingerprint_fields is None and exclude_keys or None,
            algorithm=self.params.fingerprint_algorithm,
        )

        try:
            await self.storage.upsert_fingerprint(
                identity, curr_fp, fingerprint_key=self.params.fingerprint_key
            )
        except Exception:
            pass

        return prev_fp != curr_fp

    async def process_batch(self, current_records: Iterable[Mapping[str, Any]]) -> Tuple[DiffResult, StopDecision]:
        """Convenience method: perform diff/apply and stop-evaluation in one call.

        Returns a tuple of (DiffResult, StopDecision).
        """
        # Materialize batch for counting
        batch_list = list(current_records)
        diff = await self.diff_and_apply(batch_list)
        known_in_batch = max(0, len(batch_list) - len(diff.added) - len(diff.updated))
        self.update_session_counters(
            added_count=len(diff.added), updated_count=len(diff.updated), known_in_batch=known_in_batch
        )
        decision = self.evaluate_stop_condition(batch_list)
        return diff, decision

    def evaluate_stop_condition(self, current_batch: Sequence[Mapping[str, Any]]) -> StopDecision:
        """Update stop counters and evaluate if we should stop collecting.

        Heuristics:
          - Count how many items in the batch are already known (exist in storage snapshot index).
          - If consecutive known items exceed threshold, stop.
          - If a batch produced no additions or updates (according to internal state),
            increment no-change batch counter; stop when threshold reached.
          - If total new items in the session exceed max_new_items, stop.

        Note: This method is stateless with respect to storage content (does not query DB).
        Callers should use it immediately after diff_and_apply to set accurate counters.
        """
        params = self.params
        st = self._stop_state

        # The caller is expected to compute added/updated by calling diff_and_apply first.
        # Here we infer a minimal signal: if batch length is zero -> no change.
        if len(current_batch) == 0:
            st.consecutive_no_change_batches += 1

        # Evaluate thresholds
        if params.stop_after_no_change_batches is not None and st.consecutive_no_change_batches >= params.stop_after_no_change_batches:
            return StopDecision(True, reason="no_change_batches", details={"batches": st.consecutive_no_change_batches})

        if params.max_new_items is not None and st.total_new_items_in_session >= params.max_new_items:
            return StopDecision(True, reason="max_new_items", details={"new_items": st.total_new_items_in_session})

        if params.stop_after_consecutive_known is not None and st.consecutive_known_items >= params.stop_after_consecutive_known:
            return StopDecision(True, reason="consecutive_known", details={"known": st.consecutive_known_items})

        return StopDecision(False)

    def update_session_counters(self, *, added_count: int, updated_count: int, known_in_batch: int) -> None:
        """Advance session counters to be used by stop evaluation.

        Call this right after diff_and_apply for each batch.
        known_in_batch should be the number of items already present in storage
        (i.e., batch size - added_count when deletions are not considered in the batch).
        """
        st = self._stop_state
        # New content appeared -> reset known streak
        if added_count > 0 or updated_count > 0:
            st.consecutive_known_items = 0
            st.total_new_items_in_session += added_count
            st.consecutive_no_change_batches = 0
        else:
            st.consecutive_known_items += known_in_batch
            st.consecutive_no_change_batches += 1

    def reset_session(self) -> None:  # pragma: no cover - trivial
        """重置会话状态。"""
        self._stop_state = StopState()

    async def suggest_since_timestamp(self) -> Optional[str]:
        """建议下次同步的起始时间戳。
        
        Returns:
            时间戳字符串或None
        """
        # No-op in pure fingerprint mode; kept for backward compatibility
        return None


