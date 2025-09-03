from __future__ import annotations

"""Playwright 请求克隆与重放工具

本模块提供 `NetworkRequestCloner`，用于：
- 从 Playwright 的 Response/Request 中提取并标准化请求信息（方法、URL、Query、Headers、Body）
- 支持灵活修改 query 参数与 body（JSON 或 x-www-form-urlencoded）
- 以尽可能还原的方式再次发送请求（重放），便于调试/绕过或修改部分参数后重试

注意：
- 若原请求为 multipart/form-data，工具会保留原始 body 与 headers；如需修改，请自行在 `set_raw_body` 后同步调整 `Content-Type`。
- 发送时会移除部分易冲突的 hop-by-hop 头部（如 Host/Content-Length/Connection/Accept-Encoding），由 requests 自动设置。
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple, Union
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests

from playwright.async_api import Request as PWRequest, Response as PWResponse, BrowserContext

from src.config import get_logger
from src.utils.async_utils import async_request


logger = get_logger(__name__)


# -----------------------------
# 数据结构
# -----------------------------


@dataclass
class NormalizedBody:
    """标准化的请求体表示。

    仅会填充一种表示：json_data 或 form_data 或 raw_data。
    - json_data: JSON 对象（dict/list 等）
    - form_data: application/x-www-form-urlencoded 解析后的 dict[str, Union[str, List[str]]]
    - raw_data: 无法识别或不希望解析时的原始字符串/字节串
    - content_type: Content-Type 值（若存在）
    """

    json_data: Optional[Any] = None
    form_data: Optional[Dict[str, Union[str, List[str]]]] = None
    raw_data: Optional[Union[str, bytes]] = None
    content_type: Optional[str] = None

    def is_empty(self) -> bool:
        return self.json_data is None and self.form_data is None and self.raw_data is None


@dataclass
class NormalizedRequest:
    """标准化的请求表示，便于修改与重放。"""

    method: str
    url: str
    url_scheme: str
    url_host: str
    url_path: str
    query_params: Dict[str, List[str]] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body: NormalizedBody = field(default_factory=NormalizedBody)
    cookies: List[Dict[str, Any]] = field(default_factory=list)

    def build_url(self) -> str:
        query = []
        for key, values in self.query_params.items():
            for v in values:
                query.append((key, v))
        query_str = urlencode(query, doseq=True)
        return urlunparse((self.url_scheme, self.url_host, self.url_path, "", query_str, ""))


# -----------------------------
# 工具函数
# -----------------------------


def _sanitize_headers_for_resend(headers: Mapping[str, str]) -> Dict[str, str]:
    """移除在二次请求中容易冲突/由 requests 管理的头。"""
    drop = {
        "host",
        "content-length",
        "connection",
        "accept-encoding",
        "transfer-encoding",
    }
    sanitized: Dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in drop:
            continue
        sanitized[k] = v
    return sanitized


def _parse_headers_case_insensitive(headers: Mapping[str, str]) -> Dict[str, str]:
    # Playwright headers 已是大小写不敏感的语义；此处保持原样，同时便于后续查找使用 lower 比较
    return dict(headers)


def _parse_query_params(url: str) -> Tuple[str, str, str, Dict[str, List[str]]]:
    parsed = urlparse(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query_map: Dict[str, List[str]] = {}
    for key, value in query_pairs:
        query_map.setdefault(key, []).append(value)
    return parsed.scheme, parsed.netloc, parsed.path, query_map


def _try_parse_json(text: Optional[str]) -> Optional[Any]:
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _try_parse_form(text: Optional[str]) -> Optional[Dict[str, Union[str, List[str]]]]:
    if text is None:
        return None
    try:
        pairs = parse_qsl(text, keep_blank_values=True)
        result: Dict[str, Union[str, List[str]]] = {}
        for k, v in pairs:
            if k in result:
                existing = result[k]
                if isinstance(existing, list):
                    existing.append(v)
                else:
                    result[k] = [existing, v]
            else:
                result[k] = v
        return result
    except Exception:
        return None


# -----------------------------
# 主工具类
# -----------------------------


class NetworkRequestCloner:
    """从 Playwright Request/Response 克隆请求并支持修改与重放。

    典型用法：
        page.on("response", lambda resp: ...)
        cloner = await NetworkRequestCloner.from_response(resp)
        cloner.set_query_param("cursor", "next")
        cloner.update_body_json({"page": 2})
        r = await cloner.send()
    """

    def __init__(self, normalized: NormalizedRequest) -> None:
        self._req = normalized

    # --------- 构造 ---------
    @classmethod
    async def from_response(
        cls,
        response: PWResponse,
        *,
        context: Optional[BrowserContext] = None,
    ) -> "NetworkRequestCloner":
        request = response.request
        return await cls.from_request(request, context=context)

    @classmethod
    async def from_request(
        cls,
        request: PWRequest,
        *,
        context: Optional[BrowserContext] = None,
    ) -> "NetworkRequestCloner":
        method: str = getattr(request, "method", "GET")
        url: str = getattr(request, "url", "")

        # headers: Playwright Python 里 `request.headers` 为 dict；为兼容性兜底尝试 all_headers()
        headers: Dict[str, str]
        try:
            headers = dict(getattr(request, "headers", {}) or {})
            if not headers and hasattr(request, "all_headers"):
                maybe = await request.all_headers()  # type: ignore[attr-defined]
                headers = dict(maybe or {})
        except Exception:
            headers = {}

        post_data_text: Optional[str] = None
        try:
            post_data_text = getattr(request, "post_data", None)
        except Exception:
            post_data_text = None

        content_type = None
        if headers:
            for k, v in headers.items():
                if k.lower() == "content-type":
                    content_type = v
                    break

        body = NormalizedBody(content_type=content_type)

        if post_data_text is not None and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            ct = (content_type or "").split(";")[0].strip().lower()
            if ct == "application/json":
                body.json_data = _try_parse_json(post_data_text)
                if body.json_data is None:
                    body.raw_data = post_data_text
            elif ct == "application/x-www-form-urlencoded":
                body.form_data = _try_parse_form(post_data_text)
                if body.form_data is None:
                    body.raw_data = post_data_text
            else:
                # 其他内容类型，包括 multipart/* 或 text/*
                body.raw_data = post_data_text

        scheme, host, path, query_map = _parse_query_params(url)

        normalized = NormalizedRequest(
            method=method,
            url=url,
            url_scheme=scheme,
            url_host=host,
            url_path=path,
            query_params=query_map,
            headers=_parse_headers_case_insensitive(headers),
            body=body,
        )
        # 如果提供了 context，则尝试获取该 URL 相关的 cookies
        if context is not None:
            try:
                # 仅拉取与当前 URL 相关的 cookie，避免冗余
                cookies = await context.cookies([normalized.build_url()])
                normalized.cookies = list(cookies or [])
            except Exception:
                # 容错：获取 cookies 失败时忽略
                normalized.cookies = []
        return cls(normalized)

    # --------- 读取 ---------
    def snapshot(self) -> NormalizedRequest:
        """返回当前标准化快照（浅拷贝语义由调用方控制）。"""
        return self._req

    # --------- 修改 URL / Query ---------
    def set_query_param(self, key: str, value: Union[str, List[str]]) -> None:
        if isinstance(value, list):
            self._req.query_params[key] = list(value)
        else:
            self._req.query_params[key] = [value]

    def remove_query_param(self, key: str) -> None:
        self._req.query_params.pop(key, None)

    def set_path(self, new_path: str) -> None:
        if not new_path.startswith("/"):
            new_path = "/" + new_path
        self._req.url_path = new_path

    def set_host(self, new_host: str) -> None:
        self._req.url_host = new_host

    def set_scheme(self, new_scheme: str) -> None:
        self._req.url_scheme = new_scheme

    # --------- Cookies ---------
    async def attach_cookies_from_context(self, context: BrowserContext) -> None:
        """从 BrowserContext 获取与当前 URL 相关的 cookies 并附加。"""
        try:
            cookies = await context.cookies([self._req.build_url()])
            self._req.cookies = list(cookies or [])
        except Exception:
            logger.debug("attach_cookies_from_context failed; leaving cookies unchanged")

    def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """直接设置 cookies（Playwright 风格的字典列表）。"""
        self._req.cookies = list(cookies)

    # --------- 修改 Headers ---------
    def set_header(self, key: str, value: str) -> None:
        self._req.headers[key] = value

    def remove_header(self, key: str) -> None:
        to_del = None
        for k in list(self._req.headers.keys()):
            if k.lower() == key.lower():
                to_del = k
                break
        if to_del is not None:
            self._req.headers.pop(to_del, None)

    # --------- 修改 Body ---------
    def set_raw_body(self, data: Union[str, bytes], content_type: Optional[str] = None) -> None:
        self._req.body = NormalizedBody(raw_data=data, content_type=content_type or self._req.body.content_type)

    def set_json_body(self, obj: Any) -> None:
        self._req.body = NormalizedBody(json_data=obj, content_type="application/json")

    def update_body_json(self, patch: Mapping[str, Any]) -> None:
        if self._req.body.json_data is None:
            # 若原先不是 JSON，直接设置为 JSON body
            base: Dict[str, Any] = {}
        else:
            base_data = self._req.body.json_data
            base = dict(base_data) if isinstance(base_data, dict) else {"_": base_data}
        base.update(dict(patch))
        self.set_json_body(base)

    def set_form_body(self, data: Mapping[str, Union[str, List[str]]]) -> None:
        self._req.body = NormalizedBody(form_data=dict(data), content_type="application/x-www-form-urlencoded")

    def update_body_form(self, patch: Mapping[str, Union[str, List[str]]]) -> None:
        form = dict(self._req.body.form_data or {})
        for k, v in patch.items():
            if isinstance(v, list):
                form[k] = list(v)
            else:
                form[k] = v
        self.set_form_body(form)

    # --------- 构建发送参数 ---------
    def _build_send_kwargs(self) -> Tuple[str, str, Dict[str, Any]]:
        method = self._req.method.upper()
        url = self._req.build_url()

        headers = _sanitize_headers_for_resend(self._req.headers)
        kwargs: Dict[str, Any] = {"headers": headers}

        # 如果有 cookies，则使用 RequestsCookieJar，并移除手动的 Cookie 头
        cookie_jar: Optional[requests.cookies.RequestsCookieJar] = None
        if self._req.cookies:
            # 移除显式的 Cookie 头以避免与 cookie jar 冲突
            for hk in list(headers.keys()):
                if hk.lower() == "cookie":
                    headers.pop(hk, None)
                    break

            cj = requests.cookies.RequestsCookieJar()
            for ck in self._req.cookies:
                try:
                    name = ck.get("name")
                    value = ck.get("value")
                    domain = ck.get("domain")
                    path = ck.get("path", "/")
                    secure = bool(ck.get("secure", False))
                    expires = ck.get("expires")
                    rest: Dict[str, Any] = {}
                    if "httpOnly" in ck:
                        rest["HttpOnly"] = ck.get("httpOnly")
                    if "sameSite" in ck:
                        rest["SameSite"] = ck.get("sameSite")
                    if name is None:
                        continue
                    cj.set(name=name, value=value, domain=domain, path=path, secure=secure, expires=expires, rest=rest)
                except Exception:
                    # 单个 cookie 失败不影响整体
                    continue
            cookie_jar = cj
            kwargs["cookies"] = cookie_jar

        if method in {"POST", "PUT", "PATCH", "DELETE"} and not self._req.body.is_empty():
            ct = (self._req.body.content_type or "").split(";")[0].strip().lower()
            if self._req.body.json_data is not None:
                kwargs["json"] = self._req.body.json_data
                headers.setdefault("Content-Type", "application/json")
            elif self._req.body.form_data is not None:
                # requests 会自动编码为 application/x-www-form-urlencoded
                # 如果 value 为 list，会自动展开为多值
                kwargs["data"] = self._req.body.form_data
                headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            elif self._req.body.raw_data is not None:
                kwargs["data"] = self._req.body.raw_data
                if ct:
                    headers.setdefault("Content-Type", self._req.body.content_type)

        return method, url, kwargs

    # --------- 发送 ---------
    async def send(
        self,
        *,
        method_override: Optional[str] = None,
        url_override: Optional[str] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
        timeout_sec: float = 30.0,
        session: Optional[requests.Session] = None,
    ) -> requests.Response:
        """以当前（已修改）参数发送一次 HTTP 请求。

        - 支持 method/url 覆盖
        - 支持附加额外头部（会在 sanitize 后再 merge）
        - 默认使用临时 `requests.Session()`；可传入自有 session 以复用连接与 Cookie
        """

        method, url, kwargs = self._build_send_kwargs()
        if method_override:
            method = method_override.upper()
        if url_override:
            url = url_override
        if extra_headers:
            headers = kwargs.setdefault("headers", {})
            headers.update(dict(extra_headers))

        # requests 超时参数可使用 (connect, read) 二元组
        kwargs["timeout"] = timeout_sec

        req_session = session or requests.Session()
        try:
            response: requests.Response = await async_request(req_session, method, url, **kwargs)
            return response
        finally:
            if session is None:
                try:
                    req_session.close()
                except Exception:
                    pass

    # --------- 调试导出 ---------
    def as_curl(self) -> str:
        """导出为 cURL 命令（便于调试）。"""
        method, url, kwargs = self._build_send_kwargs()
        headers = kwargs.get("headers", {})
        parts: List[str] = ["curl", "-X", method]
        for k, v in headers.items():
            parts += ["-H", f"{k}: {v}"]
        if "json" in kwargs:
            parts += ["-H", "Content-Type: application/json", "--data", json.dumps(kwargs["json"], ensure_ascii=False)]
        elif "data" in kwargs and isinstance(kwargs["data"], (str, bytes)):
            data_val = kwargs["data"]
            if isinstance(data_val, bytes):
                try:
                    data_val = data_val.decode("utf-8", errors="ignore")
                except Exception:
                    data_val = "<binary>"
            parts += ["--data", data_val]
        elif "data" in kwargs and isinstance(kwargs["data"], dict):
            parts += ["--data", urlencode(kwargs["data"], doseq=True)]
        parts.append(url)
        return " ".join(parts)


__all__ = [
    "NetworkRequestCloner",
    "NormalizedRequest",
    "NormalizedBody",
]


