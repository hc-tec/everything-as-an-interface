import asyncio
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

from ..net_rules import RuleContext, ResponseView

logger = logging.getLogger("utils.video_downloader")

CONTENT_RANGE_RE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)")


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", name).strip("._") or "video"


def _default_name_resolver(rule: RuleContext, response: ResponseView) -> str:
    url = getattr(response, "url", "video").split("?")[0]
    base = os.path.basename(url) or "video.mp4"
    if not base.lower().endswith(".mp4"):
        base += ".mp4"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{ts}_{base}"
    return _sanitize_filename(name)


@dataclass
class _ActiveDownload:
    assembler: "RangeFileAssembler"
    output_path: str
    created_ts: float


class RangeFileAssembler:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.total_size: Optional[int] = None
        self._received_ranges: list[Tuple[int, int]] = []
        self._lock = asyncio.Lock()

    async def _ensure_file(self, total_size: int) -> None:
        if self.total_size is None:
            self.total_size = total_size
            os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)
            with open(self.output_path, "wb") as f:
                f.truncate(total_size)

    @staticmethod
    def parse_content_range(header_val: Optional[str]) -> Optional[Tuple[int, int, Optional[int]]]:
        if not header_val:
            return None
        m = CONTENT_RANGE_RE.match(header_val.strip())
        if not m:
            return None
        start = int(m.group(1))
        end = int(m.group(2))
        total = None if m.group(3) == "*" else int(m.group(3))
        return start, end, total

    async def write_chunk(self, start: int, end: int, total: Optional[int], data: bytes) -> None:
        async with self._lock:
            if total is not None:
                await self._ensure_file(total)
            if self.total_size is None:
                await self._ensure_file(end + 1)
            with open(self.output_path, "r+b") as f:
                f.seek(start)
                f.write(data)
                f.flush()
            self._received_ranges.append((start, end))

    def _merged_ranges(self) -> list[Tuple[int, int]]:
        if not self._received_ranges:
            return []
        merged: list[Tuple[int, int]] = []
        for s, e in sorted(self._received_ranges):
            if not merged or s > merged[-1][1] + 1:
                merged.append((s, e))
            else:
                last_s, last_e = merged[-1]
                merged[-1] = (last_s, max(last_e, e))
        return merged

    def is_complete(self) -> bool:
        if self.total_size is None:
            return False
        merged = self._merged_ranges()
        return len(merged) == 1 and merged[0][0] == 0 and merged[0][1] + 1 == self.total_size

    def coverage_bytes(self) -> Tuple[int, Optional[int]]:
        merged = self._merged_ranges()
        covered = sum(e - s + 1 for s, e in merged) if merged else 0
        return covered, self.total_size


class BaseMediaDownloader(ABC):
    """抽象的视频下载基类。

    仅提供通用能力（去重、限速、进度、httpx/Playwright 辅助方法等）。
    具体“如何下载”的逻辑由子类实现（如 MP4 的 Range 下载、HLS 的分段下载等）。
    """

    def __init__(
        self,
        output_dir: str,
        *,
        is_target_response: Callable[[ResponseView], bool],
        name_resolver: Optional[Callable[[RuleContext, ResponseView], str]] = None,
        on_complete: Optional[Callable[[str], Any]] = None,
        on_progress: Optional[Callable[[str, int, Optional[int]], Any]] = None,
        proactive_on_first_seen: bool = False,
        default_chunk_size_bytes: int = 2 * 1024 * 1024,
        default_max_concurrency: int = 6,
        default_rate_limit_bytes_per_sec: Optional[int] = None,
        default_stream_read_size: int = 64 * 1024,
    ) -> None:
        self.output_dir = output_dir
        self.is_target_response = is_target_response
        self.name_resolver = name_resolver or _default_name_resolver
        self.on_complete = on_complete
        self.on_progress = on_progress
        self._active: Dict[str, _ActiveDownload] = {}
        self._map_lock = asyncio.Lock()
        self._last_logged_percent: Dict[str, int] = {}
        self._last_logged_time: Dict[str, float] = {}
        self.proactive_on_first_seen = proactive_on_first_seen
        self.default_chunk_size_bytes = default_chunk_size_bytes
        self.default_max_concurrency = max(1, int(default_max_concurrency))
        self._proactive_started_keys: set[str] = set()
        # 限速
        self.default_rate_limit_bps = default_rate_limit_bytes_per_sec
        self.default_stream_read_size = max(1024, int(default_stream_read_size))
        self._rate_tokens: float = float(self.default_rate_limit_bps or 0)
        self._rate_last_ts: float = time.time()
        self._rate_lock = asyncio.Lock()

    # ---------- 公共入口 ----------
    @staticmethod
    def _get_status(response: ResponseView) -> int:
        try:
            val = getattr(response, "status")
            return val() if callable(val) else int(val)
        except Exception:
            return 0

    async def on_response(self, rule: RuleContext, response: ResponseView) -> Optional[str]:
        try:
            if not self.is_target_response(response):
                return None
        except Exception:
            return None

        url: str = getattr(response, "url", "")
        ckey = self._canonical_key_from_url(url)

        if self.proactive_on_first_seen:
            if ckey not in self._proactive_started_keys:
                self._proactive_started_keys.add(ckey)
                async def _run() -> None:
                    try:
                        await self.proactive_download_from_response(response, target_url=url)
                    except Exception as exc:
                        logger.debug(f"proactive (auto) failed: {exc}")
                asyncio.create_task(_run())
            else:
                logger.debug(f"忽略重复响应（已主动中）: {ckey}")
            return None

        # 未开启主动：交由子类决定是否以及如何做被动处理
        return await self.handle_passive_response(rule, response)

    # 由子类实现的下载接口
    @abstractmethod
    async def proactive_download_from_response(
        self,
        response: ResponseView,
        *,
        filename: Optional[str] = None,
        chunk_size_bytes: int = 2 * 1024 * 1024,
        extra_headers: Optional[Dict[str, str]] = None,
        target_url: Optional[str] = None,
        max_concurrency: Optional[int] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def proactive_download_from_context(
        self,
        context: Any,
        url: str,
        *,
        filename: Optional[str] = None,
        chunk_size_bytes: int = 2 * 1024 * 1024,
        extra_headers: Optional[Dict[str, str]] = None,
        max_concurrency: Optional[int] = None,
    ) -> str:
        raise NotImplementedError

    async def handle_passive_response(self, rule: RuleContext, response: ResponseView) -> Optional[str]:
        return None

    # ---------- 内部工具 ----------
    @staticmethod
    def _canonical_key_from_url(url: str) -> str:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            host = (p.hostname or "").lower()
            scheme = (p.scheme or "http").lower()
            return f"{scheme}://{host}{p.path}"
        except Exception:
            return url

    @staticmethod
    def _sanitize_headers_for_httpx(headers: Dict[str, str], *, drop_cookies: bool = True) -> Dict[str, str]:
        banned = {"host", "connection", "transfer-encoding", "content-length", "content-encoding", "te", "upgrade", ":authority", ":method", ":path", ":scheme"}
        cleaned: Dict[str, str] = {}
        for k, v in (headers or {}).items():
            lk = k.lower().strip()
            if not lk or lk in banned or lk.startswith(":"):
                continue
            if drop_cookies and lk == "cookie":
                continue
            cleaned[lk] = v
        return cleaned

    async def _get_or_create_active(self, key: str, filename: str) -> _ActiveDownload:
        async with self._map_lock:
            existing = self._active.get(key)
            if existing:
                return existing
            output_path = os.path.join(self.output_dir, filename)
            active = _ActiveDownload(assembler=RangeFileAssembler(output_path), output_path=output_path, created_ts=time.time())
            self._active[key] = active
            logger.info(f"开始捕获: {key} -> {output_path}")
            return active

    async def _finalize_if_complete(self, key: str, active: _ActiveDownload) -> Optional[str]:
        if active.assembler.is_complete():
            async with self._map_lock:
                self._active.pop(key, None)
                self._last_logged_percent.pop(key, None)
                self._last_logged_time.pop(key, None)
            logger.info(f"下载完成: {active.output_path}")
            if self.on_complete:
                try:
                    self.on_complete(active.output_path)
                except Exception:
                    pass
            return active.output_path
        return None

    def _log_and_emit_progress(self, key: str, active: _ActiveDownload) -> None:
        covered, total = active.assembler.coverage_bytes()
        now = time.time()
        last_t = self._last_logged_time.get(key, 0)
        self._last_logged_time[key] = now
        if total and total > 0:
            percent = int(covered * 100 / total)
            last_p = self._last_logged_percent.get(key, -1)
            if percent != last_p and (percent == 100 or percent - last_p >= 1 or now - last_t > 5):
                self._last_logged_percent[key] = percent
                logger.debug(f"下载进度[{os.path.basename(active.output_path)}]: {percent}% ({covered}/{total} bytes)")
        else:
            if now - last_t > 5:
                logger.debug(f"下载进度[{os.path.basename(active.output_path)}]: {covered} bytes")
        if self.on_progress:
            try:
                self.on_progress(active.output_path, covered, total)
            except Exception:
                pass

    # ---------- httpx/Playwright 主动辅助（通用单文件 Range 工具） ----------
    @staticmethod
    def _get_total_size_from_headers(headers: Optional[Dict[str, str]]) -> Optional[int]:
        if not headers:
            return None
        try:
            cr = RangeFileAssembler.parse_content_range(headers.get("content-range"))
            if cr:
                _, _, total = cr
                return total
            cl = headers.get("content-length")
            if cl:
                return int(cl)
        except Exception:
            return None
        return None

    async def _prepare_httpx_client(self, context: Any, url: str, headers: Dict[str, str]):
        import httpx  # type: ignore
        cookies_list = await context.cookies([url])
        jar = httpx.Cookies()
        for c in cookies_list:
            try:
                jar.set(c.get("name"), c.get("value"), domain=c.get("domain"), path=c.get("path") or "/")
            except Exception:
                pass
        timeout = httpx.Timeout(30.0, read=60.0, write=30.0, connect=30.0)
        client = httpx.AsyncClient(headers=headers, cookies=jar, follow_redirects=True, timeout=timeout)
        return client

    async def _ensure_total_size_httpx(self, client: Any, url: str, *, response_headers: Optional[Dict[str, str]] = None, active: _ActiveDownload) -> int:
        total_size = self._get_total_size_from_headers(response_headers)
        if total_size:
            logger.debug(f"[httpx] 已从响应头获取总大小: {total_size} bytes")
            return total_size
        r0 = await client.get(url, headers={"Range": "bytes=0-0"})
        cr = RangeFileAssembler.parse_content_range(r0.headers.get("content-range"))
        if cr:
            _, _, total = cr
            body = r0.content
            if body:
                await active.assembler.write_chunk(0, 0, total, body[:1])
                self._log_and_emit_progress(url, active)
            logger.debug(f"[httpx] 通过 Range 0-0 探测到总大小: {total} bytes")
            return total
        r = await client.get(url)
        body = r.content
        cl = r.headers.get("content-length")
        total = int(cl) if cl else len(body)
        await active.assembler.write_chunk(0, len(body) - 1, total, body)
        self._log_and_emit_progress(url, active)
        logger.debug(f"[httpx] 整文件获取，总大小: {total} bytes")
        return total

    async def _rate_consume(self, nbytes: int, rate_bps: int) -> None:
        async with self._rate_lock:
            capacity = float(rate_bps)
            while True:
                now = time.time()
                elapsed = now - self._rate_last_ts
                if elapsed > 0:
                    self._rate_tokens = min(capacity, self._rate_tokens + elapsed * rate_bps)
                    self._rate_last_ts = now
                if self._rate_tokens >= nbytes:
                    self._rate_tokens -= nbytes
                    return
                deficit = nbytes - self._rate_tokens
                wait_s = deficit / rate_bps
                self._rate_lock.release()
                try:
                    await asyncio.sleep(wait_s)
                finally:
                    await self._rate_lock.acquire()

    async def _download_ranges_httpx(self, client: Any, url: str, *, active: _ActiveDownload, total_size: int, chunk_size_bytes: int, concurrency: int, rate_limit_bps: Optional[int], read_size: int) -> None:
        logger.info(f"[httpx] 并发分段下载开始: url={url}, 并发={concurrency}, 分块={chunk_size_bytes}")
        sem = asyncio.Semaphore(concurrency)
        async def fetch_range(start: int, end: int, attempt: int = 1) -> None:
            async with sem:
                try:
                    rng = f"bytes={start}-{end}"
                    async with client.stream("GET", url, headers={"Range": rng}) as rr:
                        if rr.status_code not in (200, 206):
                            logger.warning(f"[httpx] 分段失败 {rng} code={rr.status_code} attempt={attempt}")
                            if attempt < 3:
                                await fetch_range(start, end, attempt + 1)
                            return
                        pos = start
                        async for chunk in rr.aiter_bytes(read_size):
                            if not chunk:
                                continue
                            if rate_limit_bps:
                                await self._rate_consume(len(chunk), rate_limit_bps)
                            await active.assembler.write_chunk(pos, pos + len(chunk) - 1, total_size, chunk)
                            pos += len(chunk)
                            self._log_and_emit_progress(url, active)
                except Exception as exc:
                    logger.warning(f"[httpx] 分段异常 {start}-{end} attempt={attempt} err={exc}")
                    if attempt < 3:
                        await fetch_range(start, end, attempt + 1)
        tasks: list[asyncio.Task] = []
        pos = 0
        while pos < total_size:
            end = min(pos + chunk_size_bytes - 1, total_size - 1)
            tasks.append(asyncio.create_task(fetch_range(pos, end)))
        
            pos = end + 1
        await asyncio.gather(*tasks)
        logger.info("[httpx] 并发分段下载完成")

    async def _proactive_via_httpx(self, context: Any, url: str, *, active: _ActiveDownload, response_headers: Optional[Dict[str, str]], base_headers: Dict[str, str], chunk_size_bytes: int, max_concurrency: int, rate_limit_bps: Optional[int] = None, read_size: Optional[int] = None) -> str:
        import httpx  # type: ignore
        async with await self._prepare_httpx_client(context, url, base_headers) as client:  # type: ignore[attr-defined]
            logger.info(f"[httpx] 启动主动下载: {url}")
            total_size = await self._ensure_total_size_httpx(client, url, response_headers=response_headers, active=active)
            done = await self._finalize_if_complete(url, active)
            if done:
                return done
            await self._download_ranges_httpx(
                client,
                url,
                active=active,
                total_size=total_size,
                chunk_size_bytes=max(256 * 1024, chunk_size_bytes),
                concurrency=max(1, max_concurrency),
                rate_limit_bps=rate_limit_bps or self.default_rate_limit_bps,
                read_size=int(read_size or self.default_stream_read_size),
            )
            done = await self._finalize_if_complete(url, active)
            return done or active.output_path

    async def _proactive_via_playwright(self, context: Any, url: str, *, active: _ActiveDownload, base_headers: Dict[str, str], chunk_size_bytes: int, max_concurrency: int) -> str:
        logger.debug(f"[pw] 回退主动下载: {url}")
        total_size: Optional[int] = None
        probe_headers = {**base_headers, "Range": "bytes=0-0"}
        probe = await context.request.get(url, headers=probe_headers)
        if probe.ok:
            cr = RangeFileAssembler.parse_content_range((probe.headers or {}).get("content-range"))
            if cr:
                _, _, total = cr
                total_size = total
                body = await probe.body()
                if body:
                    await active.assembler.write_chunk(0, 0, total_size, body[:1])
                    self._log_and_emit_progress(url, active)
        if total_size is None:
            resp = await context.request.get(url, headers=base_headers)
            if not resp.ok:
                raise RuntimeError(f"Initial proactive GET failed: {resp.status}")
            headers = resp.headers or {}
            body = await resp.body()
            cr2 = RangeFileAssembler.parse_content_range(headers.get("content-range"))
            if cr2:
                start, end, total = cr2
                total_size = total or (end + 1)
                await active.assembler.write_chunk(start, end, total_size, body)
            else:
                cl = headers.get("content-length")
                total_size = int(cl) if cl else len(body)
                await active.assembler.write_chunk(0, len(body) - 1, total_size, body)
            self._log_and_emit_progress(url, active)
            done = await self._finalize_if_complete(url, active)
            if done:
                return done
        assert total_size is not None
        sem = asyncio.Semaphore(max(1, max_concurrency))
        size_per_chunk = max(256 * 1024, chunk_size_bytes)
        async def fetch_range(start: int, end: int, attempt: int = 1) -> None:
            async with sem:
                try:
                    rng = f"bytes={start}-{end}"
                    r = await context.request.get(url, headers={**base_headers, "Range": rng})
                    if not r.ok:
                        logger.warning(f"[pw] 分段失败 {rng} code={r.status} attempt={attempt}")
                        if attempt < 3:
                            await fetch_range(start, end, attempt + 1)
                        return
                    b = await r.body()
                    if not b:
                        return
                    await active.assembler.write_chunk(start, start + len(b) - 1, total_size, b)
                    self._log_and_emit_progress(url, active)
                except Exception as exc:
                    logger.warning(f"[pw] 分段异常 {start}-{end} attempt={attempt} err={exc}")
                    if attempt < 3:
                        await fetch_range(start, end, attempt + 1)
        tasks: list[asyncio.Task] = []
        pos = 0
        while pos < total_size:
            end = min(pos + size_per_chunk - 1, total_size - 1)
            tasks.append(asyncio.create_task(fetch_range(pos, end)))
            pos = end + 1
        await asyncio.gather(*tasks)
        done = await self._finalize_if_complete(url, active)
        return done or active.output_path 