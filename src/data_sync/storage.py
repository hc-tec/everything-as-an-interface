from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional


class AbstractStorage(ABC):
    """Abstract snapshot storage for sync engine.

    The storage persists the latest state of favorites and supports basic
    CRUD operations needed by the diff-and-apply workflow.
    """

    @abstractmethod
    async def get_by_id(self, identity: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    async def upsert_many(self, items: Iterable[Mapping[str, Any]]) -> int:
        ...

    @abstractmethod
    async def mark_deleted(self, identity_list: Iterable[str], *, soft_flag: str, soft_time_key: str) -> int:
        ...

    @abstractmethod
    async def delete_many(self, identity_list: Iterable[str]) -> int:
        ...

    @abstractmethod
    async def list_all_ids(self, *, id_field: str) -> List[str]:
        ...

    # Optional acceleration path for fingerprint-based detection
    async def get_fingerprint_by_id(self, identity: str, *, fingerprint_key: str) -> Optional[str]:  # pragma: no cover - optional
        return None
    async def upsert_fingerprint(self, identity: str, fingerprint: str, *, fingerprint_key: str) -> None:  # pragma: no cover - optional
        return None


class InMemoryStorage(AbstractStorage):
    """Simple in-memory storage for testing and small-scale usage."""

    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}

    async def get_by_id(self, identity: str) -> Optional[Dict[str, Any]]:
        item = self._items.get(identity)
        return dict(item) if item is not None else None

    async def upsert_many(self, items: Iterable[Mapping[str, Any]]) -> int:
        count = 0
        for it in items:
            identity = str(it.get("id"))
            self._items[identity] = dict(it)
            count += 1
        return count

    async def mark_deleted(self, identity_list: Iterable[str], *, soft_flag: str, soft_time_key: str) -> int:
        from datetime import datetime as _dt

        count = 0
        now_iso = _dt.now().isoformat()
        for identity in identity_list:
            item = self._items.get(identity)
            if item is None:
                continue
            item[soft_flag] = True
            item[soft_time_key] = now_iso
            count += 1
        return count

    async def delete_many(self, identity_list: Iterable[str]) -> int:
        count = 0
        for identity in list(identity_list):
            if identity in self._items:
                del self._items[identity]
                count += 1
        return count

    async def list_all_ids(self, *, id_field: str) -> List[str]:
        result: List[str] = []
        for it in self._items.values():
            identity = it.get(id_field)
            if identity is None:
                continue
            result.append(str(identity))
        return result

    async def get_fingerprint_by_id(self, identity: str, *, fingerprint_key: str) -> Optional[str]:
        item = self._items.get(identity)
        if not item:
            return None
        value = item.get(fingerprint_key)
        return str(value) if value is not None else None

    async def upsert_fingerprint(self, identity: str, fingerprint: str, *, fingerprint_key: str) -> None:
        item = self._items.get(identity)
        if not item:
            item = {"id": identity}
            self._items[identity] = item
        item[fingerprint_key] = fingerprint


class MongoStorage(AbstractStorage):
    """MongoDB-backed storage (optional dependency: motor)."""

    def __init__(self, *, motor_collection: Any, id_field: str = "id") -> None:
        self.col = motor_collection
        self.id_field = id_field

    async def get_by_id(self, identity: str) -> Optional[Dict[str, Any]]:
        doc = await self.col.find_one({self.id_field: identity})
        return dict(doc) if doc else None

    async def upsert_many(self, items: Iterable[Mapping[str, Any]]) -> int:
        # Use bulk_write for efficiency
        from pymongo import UpdateOne

        ops = []
        count = 0
        for it in items:
            identity = str(it.get(self.id_field))
            ops.append(
                UpdateOne({self.id_field: identity}, {"$set": dict(it)}, upsert=True)
            )
            count += 1
        if ops:
            await self.col.bulk_write(ops, ordered=False)
        return count

    async def mark_deleted(self, identity_list: Iterable[str], *, soft_flag: str, soft_time_key: str) -> int:
        from datetime import datetime as _dt

        identities = list(identity_list)
        if not identities:
            return 0
        res = await self.col.update_many(
            {self.id_field: {"$in": identities}},
            {"$set": {soft_flag: True, soft_time_key: _dt.utcnow().isoformat()}},
        )
        return int(res.modified_count or 0)

    async def delete_many(self, identity_list: Iterable[str]) -> int:
        identities = list(identity_list)
        if not identities:
            return 0
        res = await self.col.delete_many({self.id_field: {"$in": identities}})
        return int(res.deleted_count or 0)

    async def list_all_ids(self, *, id_field: str) -> List[str]:
        result: List[str] = []
        cursor = self.col.find({}, projection={id_field: 1, "_id": 0})
        async for doc in cursor:
            identity = doc.get(id_field)
            if identity is None:
                continue
            result.append(str(identity))
        return result

    async def get_fingerprint_by_id(self, identity: str, *, fingerprint_key: str) -> Optional[str]:
        doc = await self.col.find_one({self.id_field: identity}, projection={fingerprint_key: 1, "_id": 0})
        if not doc:
            return None
        value = doc.get(fingerprint_key)
        return str(value) if value is not None else None

    async def upsert_fingerprint(self, identity: str, fingerprint: str, *, fingerprint_key: str) -> None:
        await self.col.update_one(
            {self.id_field: identity},
            {"$set": {fingerprint_key: fingerprint}},
            upsert=True,
        )


