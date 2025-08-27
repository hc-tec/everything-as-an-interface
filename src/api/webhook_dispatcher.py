import asyncio
import hashlib
import hmac
import json
from src.config import get_logger
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import httpx
import requests

from src.utils.async_utils import async_request


logger = get_logger(__name__)


@dataclass
class WebhookJob:
    event_id: str
    topic_id: str
    plugin_id: Optional[str]
    payload: Dict[str, Any]
    url: str
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    attempts: int = 0
    max_attempts: int = 5
    next_delay_sec: float = 1.0


class WebhookDispatcher:
    """
    Asynchronous webhook dispatcher with in-memory queue, retries and signing.

    - At-least-once delivery semantics
    - Exponential backoff with jitter
    - HMAC-SHA256 signature header if secret provided
    - Bounded concurrency
    """

    def __init__(self, *, concurrency: int = 4, request_timeout_sec: float = 100.0) -> None:
        self._queue: "asyncio.Queue[Optional[WebhookJob]]" = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running: bool = False
        self._concurrency = max(1, concurrency)
        self._timeout = request_timeout_sec
        self._dead_letters: List[WebhookJob] = []

        # 用 requests.Session 代替 httpx.AsyncClient
        self._session = requests.Session()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("WebhookDispatcher started with concurrency=%d", self._concurrency)
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self._concurrency)]

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            await self._queue.put(None)
        for t in self._workers:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        logger.info("WebhookDispatcher stopped")

        # 关闭 session
        await asyncio.to_thread(self._session.close)

    async def enqueue(self, job: WebhookJob) -> None:
        await self._queue.put(job)

    def get_dead_letters(self) -> List[Dict[str, Any]]:
        return [self._job_to_dict(j) for j in list(self._dead_letters)]

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            job = await self._queue.get()
            if job is None:
                break
            try:
                await self._deliver_job(job)
            except Exception as e:
                logger.error("worker %d deliver error: %s", worker_id, str(e))
                await self._handle_retry(job)
            finally:
                self._queue.task_done()

    async def _deliver_job(self, job: WebhookJob) -> None:
        body = json.dumps(job.payload, ensure_ascii=False).encode("utf-8")
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "EAI-WebhookDispatcher/1.0",
            "X-EAI-Event-Id": job.event_id,
            "X-EAI-Topic-Id": job.topic_id,
        }
        if job.plugin_id:
            headers["X-EAI-Plugin-Id"] = job.plugin_id
        if job.headers:
            headers.update(job.headers)
        if job.secret:
            sig = hmac.new(job.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-EAI-Signature"] = f"sha256={sig}"

        resp = await async_request(
            self._session,
            "POST",
            job.url,
            data=body,
            headers=headers,
            timeout=self._timeout,
        )

        if 200 <= resp.status_code < 300:
            logger.info("Webhook delivered: url=%s status=%s", job.url, resp.status_code)
            return
        else:
            logger.warning("Webhook non-2xx: url=%s code=%s body=%s", job.url, resp.status_code, resp.text)
            await self._handle_retry(job)


    async def _handle_retry(self, job: WebhookJob) -> None:
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            logger.error("Webhook delivery failed permanently: url=%s attempts=%d", job.url, job.attempts)
            self._dead_letters.append(job)
            return
        # Exponential backoff with jitter (simple deterministic jitter)
        delay = min(60.0, job.next_delay_sec * 2.0)
        job.next_delay_sec = delay
        jitter = 0.5 + ((abs(hash(job.event_id)) % 100) / 100.0)
        await asyncio.sleep(delay * jitter)
        await self._queue.put(job)

    def _job_to_dict(self, job: WebhookJob) -> Dict[str, Any]:
        return {
            "event_id": job.event_id,
            "topic_id": job.topic_id,
            "plugin_id": job.plugin_id,
            "url": job.url,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
        }

