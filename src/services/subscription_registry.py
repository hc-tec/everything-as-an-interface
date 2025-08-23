import json
from src.config import get_logger
import os
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.core.subscription import SubscriptionSystem


@dataclass
class Subscription:
    id: str
    topic_id: str
    url: str
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True


class WebhookSubscriptionStore:
    """JSON-based store for webhook subscriptions (and optional topic metadata for UI).

    Core subscription logic lives in src.core.subscription.SubscriptionSystem; this store only persists
    webhook subscription records and lightweight topic metadata if desired.

    File structure example:
    {
      "topics": {"topic_id": {"name": "...", "description": "..."}},
      "subscriptions": {"sub_id": {"topic_id": "...", "url": "...", ...}}
    }
    """

    def __init__(self, file_path: str = "data/subscriptions.json", subscription_system: Optional["SubscriptionSystem"] = None) -> None:
        self.file_path = file_path
        self._data: Dict[str, Any] = {"topics": {}, "subscriptions": {}}
        self._subscription_system: Optional["SubscriptionSystem"] = subscription_system
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.error("Failed to load registry: %s", str(e))
                self._data = {"topics": {}, "subscriptions": {}}

    def _save(self) -> None:
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    # Topics
    def ensure_topic(self, topic_id: str, name: str, description: str = "") -> None:
        """Ensure topic exists. If core subscription system is present, delegate there and keep only metadata for UI.
        """
        if self._subscription_system:
            # Delegate to core system when available
            if not self._subscription_system.get_topic(topic_id):
                self._subscription_system.create_topic(name=name, description=description, topic_id=topic_id)
            # Optionally persist minimal metadata for management UIs
            self._data.setdefault("topics", {})[topic_id] = {"name": name, "description": description}
            self._save()
            return
        # Fallback to local metadata only
        self._data.setdefault("topics", {})[topic_id] = {"name": name, "description": description}
        self._save()

    def list_topics(self) -> List[Dict[str, Any]]:
        if self._subscription_system:
            return self._subscription_system.get_all_topics()
        return [{"topic_id": tid, **meta} for tid, meta in self._data.get("topics", {}).items()]

    # Subscriptions
    def add_subscription(self, topic_id: str, url: str, *, secret: Optional[str] = None, headers: Optional[Dict[str, str]] = None, enabled: bool = True) -> str:
        sub_id = str(uuid.uuid4())
        sub = Subscription(id=sub_id, topic_id=topic_id, url=url, secret=secret, headers=headers or {}, enabled=enabled)
        self._data.setdefault("subscriptions", {})[sub_id] = asdict(sub)
        self._save()
        return sub_id

    def list_subscriptions(self, topic_id: Optional[str] = None) -> List[Dict[str, Any]]:
        subs = list(self._data.get("subscriptions", {}).values())
        if topic_id:
            subs = [s for s in subs if s.get("topic_id") == topic_id]
        # Hide secrets from listing
        sanitized: List[Dict[str, Any]] = []
        for s in subs:
            s_copy = dict(s)
            if "secret" in s_copy and s_copy["secret"]:
                s_copy["secret"] = "***"
            sanitized.append(s_copy)
        return sanitized

    def get_subscription(self, sub_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get("subscriptions", {}).get(sub_id)

    def remove_subscription(self, sub_id: str) -> bool:
        if sub_id in self._data.get("subscriptions", {}):
            del self._data["subscriptions"][sub_id]
            self._save()
            return True
        return False

    def enable_subscription(self, sub_id: str, enabled: bool = True) -> bool:
        sub = self._data.get("subscriptions", {}).get(sub_id)
        if not sub:
            return False
        sub["enabled"] = enabled
        self._save()
        return True

    def get_active_subscriptions_for_topic(self, topic_id: str) -> List[Dict[str, Any]]:
        subs = [s for s in self._data.get("subscriptions", {}).values() if s.get("topic_id") == topic_id and s.get("enabled", True)]
        return list(subs)

