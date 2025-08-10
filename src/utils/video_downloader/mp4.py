from typing import Callable, Optional, Dict, Any

from .base import BaseMediaDownloader, RuleContext, ResponseView, RangeFileAssembler

class Mp4DownloadSession(BaseMediaDownloader):
    """MP4 下载会话：单文件 Range 下载实现。

    - 主动：优先 httpx 分段 Range + 并发 + 限速；回退 Playwright
    - 被动：默认不写入（若需要可覆盖 handle_passive_response）
    """

    def __init__(
        self,
        output_dir: str,
        *,
        name_resolver: Optional[Callable[[RuleContext, ResponseView], str]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[str, int, Optional[int]], None]] = None,
        proactive_on_first_seen: bool = False,
        default_chunk_size_bytes: int = 2 * 1024 * 1024,
        default_max_concurrency: int = 6,
        default_rate_limit_bytes_per_sec: Optional[int] = None,
        default_stream_read_size: int = 64 * 1024,
    ) -> None:
        def _is_mp4(resp: ResponseView) -> bool:
            try:
                headers = getattr(resp, "headers", {}) or {}
                ct = headers.get("content-type", "").lower()
                url = getattr(resp, "url", "").lower()
                return ("video/mp4" in ct) or url.endswith(".mp4")
            except Exception:
                return False

        super().__init__(
            output_dir,
            is_target_response=_is_mp4,
            name_resolver=name_resolver,
            on_complete=on_complete,
            on_progress=on_progress,
            proactive_on_first_seen=proactive_on_first_seen,
            default_chunk_size_bytes=default_chunk_size_bytes,
            default_max_concurrency=default_max_concurrency,
            default_rate_limit_bytes_per_sec=default_rate_limit_bytes_per_sec,
            default_stream_read_size=default_stream_read_size,
        )

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
        url: str = target_url or getattr(response, "url", "")
        if not url:
            raise ValueError("No URL to download")
        dummy_rule = RuleContext(pattern=__import__("re").compile(""), kind="response", match=None, func_name="proactive")
        name = filename or self.name_resolver(dummy_rule, response)
        active = await self._get_or_create_active(url, name)

        req = getattr(response, "request", None)
        if req is None:
            raise RuntimeError("Response has no associated request")
        try:
            req_headers = await req.all_headers()
        except Exception:
            req_headers = getattr(req, "headers", {}) or {}
        base_headers = {k: v for k, v in req_headers.items() if k.lower() != "range"}
        if extra_headers:
            base_headers.update(extra_headers)
        base_headers.setdefault("accept-encoding", "identity")
        base_headers = self._sanitize_headers_for_httpx(base_headers, drop_cookies=True)

        try:
            import httpx  # noqa: F401
            return await self._proactive_via_httpx(
                getattr(req, "frame").page.context,  # type: ignore[attr-defined]
                url,
                active=active,
                response_headers=getattr(response, "headers", {}) or {},
                base_headers=base_headers,
                chunk_size_bytes=chunk_size_bytes,
                max_concurrency=int(max_concurrency or self.default_max_concurrency),
                rate_limit_bps=self.default_rate_limit_bps,
                read_size=self.default_stream_read_size,
            )
        except ImportError:
            context = getattr(getattr(req, "frame"), "page").context  # type: ignore[attr-defined]
            return await self._proactive_via_playwright(
                context,
                url,
                active=active,
                base_headers=base_headers,
                chunk_size_bytes=chunk_size_bytes,
                max_concurrency=int(max_concurrency or self.default_max_concurrency),
            )

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
        class _DummyResp:
            def __init__(self, u: str) -> None:
                self.url = u
        dummy = _DummyResp(url)
        dummy_rule = RuleContext(pattern=__import__("re").compile(""), kind="response", match=None, func_name="proactive")
        name = filename or self.name_resolver(dummy_rule, dummy)  # type: ignore[arg-type]
        active = await self._get_or_create_active(url, name)

        base_headers = dict(extra_headers or {})
        base_headers.setdefault("accept-encoding", "identity")
        base_headers = self._sanitize_headers_for_httpx(base_headers, drop_cookies=True)

        try:
            import httpx  # noqa: F401
            return await self._proactive_via_httpx(
                context,
                url,
                active=active,
                response_headers=None,
                base_headers=base_headers,
                chunk_size_bytes=chunk_size_bytes,
                max_concurrency=int(max_concurrency or self.default_max_concurrency),
                rate_limit_bps=self.default_rate_limit_bps,
                read_size=self.default_stream_read_size,
            )
        except ImportError:
            return await self._proactive_via_playwright(
                context,
                url,
                active=active,
                base_headers=base_headers,
                chunk_size_bytes=chunk_size_bytes,
                max_concurrency=int(max_concurrency or self.default_max_concurrency),
            )

    async def handle_passive_response(self, rule: RuleContext, response: ResponseView) -> Optional[str]:
        # 对于 mp4，主动模式足够；被动模式可选实现（保持 None）
        return None 