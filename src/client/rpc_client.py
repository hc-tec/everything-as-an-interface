#!/usr/bin/env python3
"""
RPC风格的客户端SDK

提供类似RPC的接口，自动处理webhook注册、任务执行和结果等待。
使用示例:
    client = EAIRPCClient("http://localhost:8000", api_key="your-key")
    result = await client.chat_with_yuanbao("你好，请介绍一下自己")
    notes = await client.get_notes_brief_from_xhs(["美食", "旅行"], max_items=50)
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
import socket
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Callable, Awaitable

import httpx
import requests
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from src.utils.async_utils import async_request

logger = logging.getLogger("eai_rpc_client")


class _PendingCall:
    """等待中的RPC调用"""
    def __init__(self, event_id: str, future: asyncio.Future, timeout: float = 300.0):
        self.event_id = event_id
        self.future = future
        self.timeout = timeout
        self.created_at = time.time()
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.timeout


class _LRUIdCache:
    """LRU缓存，用于去重"""
    def __init__(self, capacity: int = 2048) -> None:
        self.capacity = capacity
        self._store: OrderedDict[str, float] = OrderedDict()

    def add_if_new(self, key: str) -> bool:
        if key in self._store:
            self._store.move_to_end(key)
            return False
        self._store[key] = time.time()
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)
        return True


class EAIRPCClient:
    """Everything-as-an-Interface RPC客户端"""
    
    def __init__(
        self, 
        base_url: str, 
        api_key: str,
        webhook_host: str = "0.0.0.0",
        webhook_port: int = 9001,
        webhook_secret: Optional[str] = None
    ):
        self._server_task = None
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.webhook_host = webhook_host
        self.webhook_port = webhook_port
        self.webhook_secret = webhook_secret or str(uuid.uuid4())
        
        # HTTP客户端
        # requests 会话
        self.http_client = requests.Session()
        self.http_client.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        })
        
        # Webhook服务器
        self.webhook_app = FastAPI(title="EAI RPC Webhook Receiver")
        self._setup_webhook_routes()
        
        # 等待中的调用
        self._pending_calls: Dict[str, _PendingCall] = {}
        self._events_seen = _LRUIdCache()
        
        # 服务器状态
        self._webhook_server: Optional[uvicorn.Server] = None
        self._cleanup_task = None
    
    def _setup_webhook_routes(self):
        """设置webhook路由"""
        @self.webhook_app.get("/health")
        async def health_check():
            """健康检查端点"""
            return {"status": "ok", "service": "eai-rpc-webhook"}
        
        @self.webhook_app.post("/webhook")
        async def receive_webhook(
            request: Request,
            x_eai_event_id: Optional[str] = Header(default=None),
            x_eai_signature: Optional[str] = Header(default=None),
            x_eai_topic_id: Optional[str] = Header(default=None),
            x_eai_plugin_id: Optional[str] = Header(default=None),
        ) -> Dict[str, Any]:
            raw = await request.body()
            
            # 验证签名
            if self.webhook_secret and x_eai_signature:
                if not self._verify_signature(self.webhook_secret, raw, x_eai_signature):
                    raise HTTPException(status_code=401, detail="Invalid signature")
            
            # 去重
            event_id = x_eai_event_id or ""
            if event_id:
                is_new = self._events_seen.add_if_new(event_id)
                if not is_new:
                    return {"ok": True, "duplicate": True}
            
            # 解析payload
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {"raw": raw.decode("utf-8", errors="replace")}
            
            # 处理等待中的调用（通过topic_id匹配）
            match_key = x_eai_topic_id
            if match_key in self._pending_calls:
                pending = self._pending_calls.pop(match_key)
                if not pending.future.done():
                    result = payload.get("result", {})
                    if payload.get("success", True):
                        pending.future.set_result(result)
                    else:
                        error_msg = payload.get("error", "Unknown error")
                        pending.future.set_exception(Exception(error_msg))
            
            logger.info(
                "Received webhook: event_id=%s, topic_id=%s, plugin_id=%s",
                event_id, x_eai_topic_id, x_eai_plugin_id
            )
            
            return {"ok": True}
    
    def _verify_signature(self, secret: str, raw_body: bytes, signature_header: str) -> bool:
        """验证HMAC签名"""
        try:
            scheme, hexdigest = signature_header.split("=", 1)
            if scheme.lower() != "sha256":
                return False
            expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, hexdigest)
        except Exception:
            return False
    
    async def _cleanup_expired_calls(self):
        """清理过期的调用"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                expired_keys = []
                for event_id, pending in self._pending_calls.items():
                    if pending.is_expired():
                        expired_keys.append(event_id)
                        if not pending.future.done():
                            pending.future.set_exception(TimeoutError("RPC call timeout"))
                
                for key in expired_keys:
                    self._pending_calls.pop(key, None)
                    
            except Exception as e:
                logger.error("Error in cleanup task: %s", e)
    
    async def start(self):
        """启动webhook服务器"""

        # 如果端口为0，自动分配可用端口
        if self.webhook_port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', 0))
            self.webhook_port = sock.getsockname()[1]
            sock.close()
        
        config = uvicorn.Config(
            self.webhook_app,
            host=self.webhook_host,
            port=self.webhook_port,
            log_level="warning"  # 减少日志输出
        )
        self._webhook_server = uvicorn.Server(config)
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_calls())
        
        # 在后台启动服务器
        self._server_task = asyncio.create_task(self._webhook_server.serve())

    async def stop(self):
        """停止服务"""
        if self._cleanup_task:
            try:
                await self._cleanup_task.cancel()
            except asyncio.CancelledError:
                pass
            except TypeError:
                pass
        
        if hasattr(self, '_server_task') and self._server_task:
            try:
                await self._server_task.cancel()
            except asyncio.CancelledError:
                pass
            except TypeError:
                pass
        
        if self._webhook_server:
            self._webhook_server.should_exit = True
            await self._webhook_server.shutdown()
        
        await asyncio.to_thread(self.http_client.close)
    
    @asynccontextmanager
    async def _rpc_call(self, plugin_id: str, config: Dict[str, Any], timeout: float = 30.0):
        """执行RPC调用的上下文管理器"""
        # 生成唯一的事件ID
        event_id = str(uuid.uuid4())

        await self._test_health()
        
        # 创建topic
        topic_id = f"rpc-{event_id}"
        await self._create_topic(topic_id, f"RPC call for {plugin_id}")
        
        # 创建subscription
        webhook_host = self.webhook_host
        webhook_url = f"http://{webhook_host}:{self.webhook_port}/webhook"
        await self._create_subscription(topic_id, webhook_url)
        
        # 创建Future等待结果
        future = asyncio.Future()
        pending = _PendingCall(topic_id, future, timeout)
        # 将pending挂载在topic_id下，方便通过topic_id回填结果
        self._pending_calls[topic_id] = pending
        
        try:
            # 执行插件
            await self._run_plugin(plugin_id, config, topic_id)
            
            # 等待结果
            result = await asyncio.wait_for(future, timeout=timeout)
            yield result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"RPC call timeout after {timeout} seconds")
        finally:
            # 清理
            self._pending_calls.pop(topic_id, None)

    async def _test_health(self):
        """测试是否正常连接"""
        response = await async_request(self.http_client, "GET", f"{self.base_url}/api/v1/health", timeout=30)
        try:
            ret = response.json()
            if ret.get("status") == "ok":
                print("与服务连接正常")
            else:
                raise RuntimeError()
        except Exception:
            print("服务似乎未正常启动")
        response.raise_for_status()
    
    async def _create_topic(self, topic_id: str, description: str):
        """创建topic"""
        response = await async_request(
            self.http_client,
            "post",
            f"{self.base_url}/api/v1/topics",
            json={
                "topic_id": topic_id,
                "name": topic_id,
                "description": description
            },
            timeout=30)
        response.raise_for_status()
    
    async def _create_subscription(self, topic_id: str, webhook_url: str):
        """创建subscription"""
        response = await async_request(
            self.http_client,
            "post",
            f"{self.base_url}/api/v1/topics/{topic_id}/subscriptions",
            json={
                "url": webhook_url,
                "secret": self.webhook_secret,
                "headers": {},
                "enabled": True
            },
            timeout=30)
        response.raise_for_status()
    
    async def _run_plugin(self, plugin_id: str, config: Dict[str, Any], topic_id: str):
        """运行插件"""
        response = await async_request(
            self.http_client,
            "post",
            f"{self.base_url}/api/v1/plugins/{plugin_id}/run",
            json={
                "config": config,
                "topic_id": topic_id
            },
            timeout=30)
        response.raise_for_status()
    
    # 具体的RPC方法
    async def chat_with_yuanbao(self, message: str, **kwargs) -> Dict[str, Any]:
        """与AI元宝聊天"""
        config = {
            "ask_question": message,
            "headless": kwargs.get("headless", False),
            **kwargs
        }
        async with self._rpc_call("yuanbao_chat", config) as result:
            return result
    
    async def get_notes_brief_from_xhs(
        self,
        storage_file: str,
        max_items: int = 20,
        max_seconds: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """从小红书获取笔记摘要"""
        config = {
            "storage_file": storage_file,
            "max_items": max_items,
            "max_seconds": max_seconds,
            "headless": kwargs.get("headless", False),
            "cookie_ids": kwargs.get("cookie_ids", []),
            **kwargs
        }
        
        async with self._rpc_call("xiaohongshu_brief", config) as result:
            return result
    
    async def get_notes_details_from_xhs(
        self, 
        keywords: List[str], 
        max_items: int = 20,
        max_seconds: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """从小红书获取笔记详情"""
        config = {
            "task_type": "details", 
            "search_keywords": keywords,
            "max_items": max_items,
            "max_seconds": max_seconds,
            "headless": kwargs.get("headless", False),
            "cookie_ids": kwargs.get("cookie_ids", []),
            **kwargs
        }
        
        async with self._rpc_call("xiaohongshu_details", config) as result:
            return result
    
    async def search_notes_from_xhs(
        self, 
        keywords: List[str], 
        max_items: int = 20,
        max_seconds: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """从小红书搜索笔记"""
        config = {
            "search_keywords": keywords,
            "max_items": max_items,
            "max_seconds": max_seconds,
            "headless": kwargs.get("headless", False),
            "cookie_ids": kwargs.get("cookie_ids", []),
            **kwargs
        }
        
        async with self._rpc_call("xiaohongshu_search", config) as result:
            return result
    
    async def get_favorites_from_xhs(
        self, 
        max_items: int = 20,
        max_seconds: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """从小红书获取收藏"""
        config = {
            "task_type": "favorites",
            "max_items": max_items,
            "max_seconds": max_seconds,
            "headless": kwargs.get("headless", False),
            "cookie_ids": kwargs.get("cookie_ids", []),
            **kwargs
        }
        
        async with self._rpc_call("xiaohongshu", config) as result:
            return result
    
    # 通用插件调用方法
    async def call_plugin(
        self, 
        plugin_id: str, 
        config: Dict[str, Any], 
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """通用插件调用方法"""
        async with self._rpc_call(plugin_id, config, timeout) as result:
            return result


# 便捷的同步包装器
class EAIRPCClientSync:
    """同步版本的RPC客户端"""
    
    def __init__(self, *args, **kwargs):
        self._client = EAIRPCClient(*args, **kwargs)
        self._loop = None
    
    def _ensure_loop(self):
        if self._loop is None:
            # self._loop = asyncio.get_event_loop()
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def start(self):
        self._ensure_loop()
        return self._loop.run_until_complete(self._client.start())
    
    def stop(self):
        if self._loop:
            return self._loop.run_until_complete(self._client.stop())
    
    def chat_with_yuanbao(self, message: str, **kwargs) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.chat_with_yuanbao(message, **kwargs)
        )
    
    def get_notes_brief_from_xhs(
        self, 
        keywords: List[str], 
        max_items: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.get_notes_brief_from_xhs(keywords, max_items, **kwargs)
        )
    
    def get_notes_details_from_xhs(
        self, 
        keywords: List[str], 
        max_items: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.get_notes_details_from_xhs(keywords, max_items, **kwargs)
        )
    
    def search_notes_from_xhs(
        self, 
        keywords: List[str], 
        max_items: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.search_notes_from_xhs(keywords, max_items, **kwargs)
        )
    
    def get_favorites_from_xhs(
        self, 
        max_items: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.get_favorites_from_xhs(max_items, **kwargs)
        )
    
    def call_plugin(
        self, 
        plugin_id: str, 
        config: Dict[str, Any], 
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._client.call_plugin(plugin_id, config, timeout)
        )