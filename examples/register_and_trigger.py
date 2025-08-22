#!/usr/bin/env python3
"""
Client script to:
 1) Create a topic
 2) Register a webhook subscription
 3) Send a test delivery

Requirements:
  - Server running at BASE_URL
  - Set API_KEY to match server (EAI_API_KEY)
  - WEBHOOK_URL points to your webhook receiver (e.g., http://localhost:9000/webhook)

Usage:
  python examples/register_and_trigger.py
"""

import os
import sys
import json
import uuid
from typing import Any, Dict

import httpx


BASE_URL = os.getenv("EAI_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("EAI_API_KEY", "testkey")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:9000/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret-demo")


def _headers() -> Dict[str, str]:
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        # 1) Create topic
        name = f"demo-topic-{uuid.uuid4().hex[:8]}"
        resp = client.post(
            f"{BASE_URL}/api/v1/topics",
            headers=_headers(),
            json={"name": name, "description": "demo topic from client"},
        )
        resp.raise_for_status()
        topic_id = resp.json()["topic_id"]
        print(f"Created topic: {topic_id} ({name})")

        # 2) Create subscription
        sub = client.post(
            f"{BASE_URL}/api/v1/topics/{topic_id}/subscriptions",
            headers=_headers(),
            json={
                "url": WEBHOOK_URL,
                "secret": WEBHOOK_SECRET,
                "headers": {"X-Demo": "client"},
            },
        )
        sub.raise_for_status()
        subscription_id = sub.json()["subscription_id"]
        print(f"Registered subscription: {subscription_id}")

        # 3) Test delivery
        test = client.post(
            f"{BASE_URL}/api/v1/subscriptions/test-delivery",
            headers=_headers(),
            params={"topic_id": topic_id},
        )
        test.raise_for_status()
        print("Test delivery enqueued:", test.json())

        print("\nNext: try running a plugin or task bound to this topic to see real payloads.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print("HTTP error:", e, file=sys.stderr)
        sys.exit(1)
