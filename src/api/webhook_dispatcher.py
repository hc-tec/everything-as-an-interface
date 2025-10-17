import asyncio
import hashlib
import hmac
import json
import uuid
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
    - Automatic payload chunking for large payloads
    """

    def __init__(self, *, concurrency: int = 4, request_timeout_sec: float = 100.0, max_chunk_size_bytes: int = 800_000) -> None:
        self._queue: "asyncio.Queue[Optional[WebhookJob]]" = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running: bool = False
        self._concurrency = max(1, concurrency)
        self._timeout = request_timeout_sec
        self._max_chunk_size = max_chunk_size_bytes
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
                await self._deliver_job_with_chunking(job)
            except Exception as e:
                logger.error("worker %d deliver error: %s", worker_id, str(e))
                await self._handle_retry(job)
            finally:
                self._queue.task_done()

    def _chunk_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a large payload into smaller chunks.

        Strategy:
        - If payload has a 'result' field with a list, split by items
        - Otherwise, estimate and split the JSON string

        Returns a list of chunk payloads with metadata.
        """
        # First, check if chunking is needed
        test_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(test_body) <= self._max_chunk_size:
            return [payload]  # No chunking needed

        logger.info("Payload size %d exceeds max chunk size %d, chunking required", len(test_body), self._max_chunk_size)

        # Try to chunk the 'result' field if it's a list
        result = payload.get("result", {})
        if isinstance(result, dict) and "items" in result and isinstance(result["items"], list):
            # Common pattern: result has an 'items' array
            return self._chunk_result_items(payload, result["items"])
        elif isinstance(result, list):
            # result is directly a list
            return self._chunk_result_items(payload, result)
        else:
            # Fallback: cannot intelligently chunk, split JSON string
            logger.warning("Cannot intelligently chunk payload, result is not a list")
            return self._chunk_json_string(payload)

    def _chunk_result_items(self, payload: Dict[str, Any], items: List[Any]) -> List[Dict[str, Any]]:
        """
        Chunk a payload by splitting its result items array.
        """
        chunks: List[Dict[str, Any]] = []
        base_payload = dict(payload)
        result = base_payload.get("result", {})

        # Estimate overhead (payload without items)
        if isinstance(result, dict):
            result_without_items = {k: v for k, v in result.items() if k != "items"}
        else:
            result_without_items = []

        base_payload_copy = dict(base_payload)
        base_payload_copy["result"] = result_without_items
        base_size = len(json.dumps(base_payload_copy, ensure_ascii=False).encode("utf-8"))

        # Add chunking metadata overhead estimate (200 bytes)
        overhead = base_size + 200
        available_size = self._max_chunk_size - overhead

        # Estimate average item size
        if len(items) > 0:
            sample_size = min(10, len(items))
            sample_items = items[:sample_size]
            sample_bytes = len(json.dumps(sample_items, ensure_ascii=False).encode("utf-8"))
            avg_item_size = sample_bytes / sample_size
            items_per_chunk = max(1, int(available_size / avg_item_size))
        else:
            items_per_chunk = 1

        logger.info("Chunking %d items into chunks of ~%d items each", len(items), items_per_chunk)

        # Split items into chunks
        for i in range(0, len(items), items_per_chunk):
            chunk_items = items[i:i + items_per_chunk]
            chunk_payload = dict(base_payload)

            # Reconstruct result with chunk items
            if isinstance(result, dict):
                chunk_result = dict(result)
                chunk_result["items"] = chunk_items
                chunk_payload["result"] = chunk_result
            else:
                chunk_payload["result"] = chunk_items

            chunks.append(chunk_payload)

        # Add chunk metadata to all chunks
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            chunk["is_chunked"] = True
            chunk["chunk_index"] = idx
            chunk["total_chunks"] = total_chunks
            chunk["chunk_id"] = str(uuid.uuid4())

        logger.info("Payload split into %d chunks", total_chunks)
        return chunks

    def _chunk_json_string(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback: split payload by truncating JSON string (not ideal but works).
        This is a simple implementation - a production version might be smarter.
        """
        # For now, just return the original payload and log a warning
        # In production, you might want to implement string-level splitting
        logger.error("String-level chunking not implemented, sending oversized payload")
        return [payload]

    async def _deliver_job_with_chunking(self, job: WebhookJob) -> None:
        """
        Deliver a job, automatically chunking if the payload is too large.
        """
        chunks = self._chunk_payload(job.payload)

        if len(chunks) == 1:
            # No chunking needed
            await self._deliver_job(job)
        else:
            # Deliver each chunk as a separate webhook
            for chunk_payload in chunks:
                chunk_job = WebhookJob(
                    event_id=job.event_id,  # Keep same event_id for reassembly
                    topic_id=job.topic_id,
                    plugin_id=job.plugin_id,
                    payload=chunk_payload,
                    url=job.url,
                    secret=job.secret,
                    headers=job.headers,
                    attempts=job.attempts,
                    max_attempts=job.max_attempts,
                    next_delay_sec=job.next_delay_sec,
                )
                await self._deliver_job(chunk_job)

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

