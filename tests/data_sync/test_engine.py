import asyncio
from datetime import datetime, timedelta

import pytest

from src.data_sync.engine import PassiveSyncEngine
from src.data_sync.models import SyncConfig
from src.data_sync.storage import InMemoryStorage


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()

@pytest.mark.asyncio
async def test_full_snapshot_then_incremental_add_update_delete():
    storage = InMemoryStorage()
    engine = PassiveSyncEngine(storage=storage, config=SyncConfig(identity_key="id"))

    t0 = datetime.utcnow() - timedelta(days=1)
    t1 = datetime.utcnow()
    t2 = datetime.utcnow() + timedelta(seconds=10)

    # First full batch (empty storage -> all added)
    batch1 = [
        {"id": "a", "title": "A1"},
        {"id": "b", "title": "B1"},
    ]
    diff1 = await engine.diff_and_apply(batch1)
    assert {d["id"] for d in diff1.added} == {"a", "b"}
    assert diff1.updated == []
    assert diff1.deleted == []

    # Second batch: add c, update a, delete b (not present)
    batch2 = [
        {"id": "a", "title": "A2"},  # updated by fingerprint
        {"id": "c", "title": "C1"},  # new
    ]
    diff2 = await engine.diff_and_apply(batch2)
    assert {d["id"] for d in diff2.added} == {"c"}
    assert {d["id"] for d in diff2.updated} == {"a"}
    # b missing -> deleted (soft)
    assert {d["id"] for d in diff2.deleted} == {"b"}


@pytest.mark.asyncio
async def test_update_detection_without_timestamp_fallback_deep_compare():
    storage = InMemoryStorage()
    engine = PassiveSyncEngine(storage=storage, config=SyncConfig(identity_key="id"))

    # Seed one document without updated_at
    batch1 = [
        {"id": "a", "title": "A1"},
    ]
    _ = await engine.diff_and_apply(batch1)

    # Same content -> no update
    diff_same = await engine.diff_and_apply([{"id": "a", "title": "A1"}])
    assert diff_same.added == [] and diff_same.updated == []

    # Changed content -> should be updated
    diff_change = await engine.diff_and_apply([{"id": "a", "title": "A2"}])
    assert {d["id"] for d in diff_change.updated} == {"a"}


@pytest.mark.asyncio
async def test_fingerprint_update_detection_without_timestamp():
    storage = InMemoryStorage()
    # prefer_fingerprint True by default; make sure fingerprint_fields defaults to all non-bookkeeping fields
    cfg = SyncConfig(identity_key="id")
    engine = PassiveSyncEngine(storage=storage, config=cfg)

    # Seed a doc with no updated_at
    _ = await engine.diff_and_apply([
        {"id": "x", "title": "Hello", "tags": [1, 2, 3]},
    ])

    # Same content -> no update
    d_same = await engine.diff_and_apply([
        {"id": "x", "title": "Hello", "tags": [1, 2, 3]},
    ])
    assert d_same.updated == []

    # Content changed -> update
    d_changed = await engine.diff_and_apply([
        {"id": "x", "title": "Hello World", "tags": [1, 2, 3]},
    ])
    assert {r["id"] for r in d_changed.updated} == {"x"}

    # Change an order-insensitive structure but serialized deterministically -> still detects
    d_changed2 = await engine.diff_and_apply([
        {"id": "x", "title": "Hello World", "tags": [3, 2, 1]},
    ])
    assert {r["id"] for r in d_changed2.updated} == {"x"}


@pytest.mark.asyncio
async def test_fingerprint_fields_limits_scope():
    storage = InMemoryStorage()
    cfg = SyncConfig(identity_key="id", fingerprint_fields=["title"])  # only title participates in fp
    engine = PassiveSyncEngine(storage=storage, config=cfg)

    _ = await engine.diff_and_apply([
        {"id": "n1", "title": "T1", "extra": {"a": 1}},
    ])
    # Change only extra -> should NOT update because fingerprint ignores it
    d = await engine.diff_and_apply([
        {"id": "n1", "title": "T1", "extra": {"a": 2}},
    ])
    assert d.updated == []
    # Change title -> should update
    d2 = await engine.diff_and_apply([
        {"id": "n1", "title": "T2", "extra": {"a": 2}},
    ])
    assert {r["id"] for r in d2.updated} == {"n1"}


@pytest.mark.asyncio
async def test_stop_conditions():
    storage = InMemoryStorage()
    cfg = SyncConfig(
        identity_key="id",
        stop_after_consecutive_known=3,
        stop_after_no_change_batches=2,
        max_new_items=2,
    )
    engine = PassiveSyncEngine(storage=storage, config=cfg)

    t = iso(datetime.utcnow())

    # Batch 1: add 2 items -> reach max_new_items
    d1 = await engine.diff_and_apply([{"id": "a", "title": "A"}, {"id": "b", "title": "B"}])
    engine.update_session_counters(added_count=len(d1.added), updated_count=len(d1.updated), known_in_batch=0)
    decision1 = engine.evaluate_stop_condition([{"id": "a"}, {"id": "b"}])
    assert decision1.should_stop and decision1.reason == "max_new_items"

    # Reset session and test consecutive known items
    engine.reset_session()
    # Batch 2: no new/updates, 3 known items in a row -> stop
    d2 = await engine.diff_and_apply([{"id": "a", "title": "A"}, {"id": "b", "title": "B"}, {"id": "a", "title": "A"}])
    engine.update_session_counters(added_count=len(d2.added), updated_count=len(d2.updated), known_in_batch=3)
    decision2 = engine.evaluate_stop_condition([{"id": "a"}, {"id": "b"}, {"id": "a"}])
    assert decision2.should_stop and decision2.reason == "consecutive_known"

    # Reset session and test no-change batches
    engine.reset_session()
    _ = await engine.diff_and_apply([{"id": "a", "title": "A"}])
    engine.update_session_counters(added_count=0, updated_count=0, known_in_batch=1)
    _ = engine.evaluate_stop_condition([{"id": "a"}])
    # Second no-change batch triggers stop
    _ = await engine.diff_and_apply([{"id": "a", "title": "A"}])
    engine.update_session_counters(added_count=0, updated_count=0, known_in_batch=1)
    decision3 = engine.evaluate_stop_condition([{"id": "a"}])
    assert decision3.should_stop and decision3.reason == "no_change_batches"


@pytest.mark.asyncio
async def test_process_batch_and_suggest_since_timestamp():
    storage = InMemoryStorage()
    engine = PassiveSyncEngine(storage=storage, config=SyncConfig(identity_key="id"))

    ts1 = iso(datetime.utcnow() - timedelta(days=1))
    ts2 = iso(datetime.utcnow())

    diff1, decision1 = await engine.process_batch([{"id": "a", "title": "A1"}])
    assert len(diff1.added) == 1 and not decision1.should_stop

    diff2, decision2 = await engine.process_batch([{"id": "a", "title": "A2"}])
    assert len(diff2.updated) == 1

    since = await engine.suggest_since_timestamp()
    assert since is None


