#!/usr/bin/env python3
"""
Minimal webhook receiver (best practices):
 - Verifies HMAC-SHA256 signature if WEBHOOK_SECRET is set
 - Ensures idempotency via in-memory event cache
 - Fast, resilient handler that returns 2xx quickly

Run:
  export WEBHOOK_SECRET=your-secret  # optional
  uvicorn examples.webhook_receiver:app --host 0.0.0.0 --port 9000 --reload
"""

import hashlib
import hmac
import json
from src.config import get_logger
import os
import time
from collections import OrderedDict
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request


logger = get_logger(__name__)

app = FastAPI(title="Webhook Receiver")


class _LRUIdCache:
    def __init__(self, capacity: int = 2048) -> None:
        self.capacity = capacity
        self._store: OrderedDict[str, float] = OrderedDict()

    def add_if_new(self, key: str) -> bool:
        # returns True if newly added, False if exists
        if key in self._store:
            # move to end (most recent)
            self._store.move_to_end(key)
            return False
        self._store[key] = time.time()
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)
        return True


_events_seen = _LRUIdCache()


def _verify_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    try:
        scheme, hexdigest = signature_header.split("=", 1)
        if scheme.lower() != "sha256":
            return False
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        # timing-safe compare
        return hmac.compare_digest(expected, hexdigest)
    except Exception:
        return False


@app.post("/webhook")
async def receive(
    request: Request,
    x_eai_event_id: str | None = Header(default=None, convert_underscores=False),
    x_eai_signature: str | None = Header(default=None, convert_underscores=False),
    x_eai_topic_id: str | None = Header(default=None, convert_underscores=False),
    x_eai_plugin_id: str | None = Header(default=None, convert_underscores=False),
) -> Dict[str, Any]:
    raw = await request.body()

    # 1) Optional signature verification
    secret = os.getenv("WEBHOOK_SECRET")
    if secret:
        if not x_eai_signature or not _verify_signature(secret, raw, x_eai_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # 2) Idempotency: dedupe by event id
    event_id = x_eai_event_id or ""
    if event_id:
        is_new = _events_seen.add_if_new(event_id)
        if not is_new:
            # Already processed; respond 200 for at-least-once semantics
            return {"ok": True, "duplicate": True}

    # 3) Parse JSON payload
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        payload = {"raw": raw.decode("utf-8", errors="replace")}

    # 4) Persist optionally (demo): write to ./data/webhook_events
    try:
        from pathlib import Path

        out_dir = Path("data/webhook_events")
        out_dir.mkdir(parents=True, exist_ok=True)
        name = event_id or str(int(time.time() * 1000))
        with open(out_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("failed to persist payload: %s", e)

    # 5) Do your business logic here quickly, or enqueue for later processing
    # For demo, just log a concise line
    logger.info(
        "received event id=%s topic=%s plugin=%s success=%s",
        event_id,
        x_eai_topic_id,
        x_eai_plugin_id,
        bool(payload.get("result", {}).get("success")),
    )

    return {"ok": True}

