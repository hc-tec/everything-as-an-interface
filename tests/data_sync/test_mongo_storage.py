import os
from datetime import datetime, timedelta
from uuid import uuid4
import pytest

from src.data_sync import PassiveSyncEngine, SyncConfig, MongoStorage

def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


@pytest.fixture
async def mongo_col():
    motor = pytest.importorskip("motor.motor_asyncio", reason="motor is required for MongoDB tests")
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = motor.AsyncIOMotorClient(uri, uuidRepresentation="standard", serverSelectionTimeoutMS=500)
    try:
        await client.admin.command("ping")
    except Exception:
        pytest.skip("MongoDB server is not available on localhost:27017")

    db_name = f"eai_test_{uuid4().hex[:8]}"
    col = client[db_name]["notes"]
    yield col
    await client.drop_database(db_name)
    client.close()


@pytest.mark.asyncio
async def test_mongo_soft_delete_flow(mongo_col):
    mongo_col = await anext(mongo_col)

    storage = MongoStorage(motor_collection=mongo_col, id_field="id")
    engine = PassiveSyncEngine(
        storage=storage,
        config=SyncConfig(identity_key="id", deletion_policy="soft"),
    )

    t0 = datetime.utcnow() - timedelta(days=1)
    t1 = datetime.utcnow()
    t2 = datetime.utcnow() + timedelta(seconds=10)

    # First batch: add a, b
    batch1 = [
        {"id": "a", "title": "A1"},
        {"id": "b", "title": "B1"},
    ]
    diff1 = await engine.diff_and_apply(batch1)
    assert {d["id"] for d in diff1.added} == {"a", "b"}
    assert not diff1.updated and not diff1.deleted

    # Second batch: update a, add c, b disappears -> soft deleted
    batch2 = [
        {"id": "a", "title": "A2"},
        {"id": "c", "title": "C1"},
    ]
    diff2 = await engine.diff_and_apply(batch2)
    assert {d["id"] for d in diff2.added} == {"c"}
    assert {d["id"] for d in diff2.updated} == {"a"}
    assert {d["id"] for d in diff2.deleted} == {"b"}

    # Check soft delete flags persisted
    b_doc = await mongo_col.find_one({"id": "b"})
    assert b_doc is not None
    assert b_doc.get("deleted") is True
    assert isinstance(b_doc.get("deleted_at"), str)


@pytest.mark.asyncio
async def test_mongo_hard_delete_flow(mongo_col):
    mongo_col = await anext(mongo_col)

    storage = MongoStorage(motor_collection=mongo_col, id_field="id")
    engine = PassiveSyncEngine(
        storage=storage,
        config=SyncConfig(identity_key="id", deletion_policy="hard"),
    )

    t = datetime.utcnow()

    # Seed two
    _ = await engine.diff_and_apply([
        {"id": "x", "title": "X1"},
        {"id": "y", "title": "Y1"},
    ])

    # Next batch: keep only x -> y should be physically deleted
    diff = await engine.diff_and_apply([
        {"id": "x", "title": "X1"},
    ])
    assert {d["id"] for d in diff.deleted} == {"y"}

    y_doc = await mongo_col.find_one({"id": "y"})
    assert y_doc is None


