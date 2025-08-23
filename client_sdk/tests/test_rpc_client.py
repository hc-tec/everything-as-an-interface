#!/usr/bin/env python3
"""
RPC客户端测试

测试RPC客户端的基本功能，包括连接、调用和错误处理。
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from client_sdk.rpc_client import EAIRPCClient, EAIRPCClientSync, _PendingCall, _LRUIdCache


class TestLRUIdCache:
    """测试LRU缓存"""
    
    def test_add_new_item(self):
        cache = _LRUIdCache(capacity=3)
        assert cache.add_if_new("key1") is True
        assert cache.add_if_new("key1") is False  # 重复添加
    
    def test_capacity_limit(self):
        cache = _LRUIdCache(capacity=2)
        
        # 测试基本添加
        assert cache.add_if_new("key1") is True
        assert cache.add_if_new("key2") is True
        assert len(cache._store) == 2
        
        # 重复添加应该返回False
        assert cache.add_if_new("key1") is False  # key1移动到末尾
        assert cache.add_if_new("key2") is False  # key2移动到末尾
        
        # 添加第三个key，应该移除最老的key
        assert cache.add_if_new("key3") is True
        assert len(cache._store) == 2
        
        # 验证LRU行为：key1应该被移除了
        assert "key1" not in cache._store
        assert "key2" in cache._store
        assert "key3" in cache._store


class TestPendingCall:
    """测试等待中的调用"""
    
    def test_expiration(self):
        # 创建一个事件循环来避免警告
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = asyncio.Future()
            pending = _PendingCall("test-id", future, timeout=0.1)
            
            assert not pending.is_expired()
            time.sleep(0.2)
            assert pending.is_expired()
        finally:
            loop.close()
            asyncio.set_event_loop(None)


class TestEAIRPCClient:
    """测试RPC客户端"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return EAIRPCClient(
            base_url="http://localhost:8008",
            api_key="testkey",
            webhook_host="127.0.0.1",
            webhook_port=9999
        )

    def test_client_initialization(self, client):
        """测试客户端初始化"""
        assert client.base_url == "http://localhost:8008"
        assert client.api_key == "testkey"
        assert client.webhook_host == "127.0.0.1"
        assert client.webhook_port == 9999
        assert client.webhook_secret is not None
    
    def test_verify_signature(self, client):
        """测试签名验证"""
        secret = "test-secret"
        message = b"test message"
        
        # 生成正确的签名
        import hmac
        import hashlib
        expected_sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        signature_header = f"sha256={expected_sig}"
        
        assert client._verify_signature(secret, message, signature_header) is True
        assert client._verify_signature(secret, message, "sha256=wrong") is False
        assert client._verify_signature(secret, message, "invalid") is False
    
    @pytest.mark.asyncio
    async def test_create_topic(self, client):
        """测试创建topic"""
        with patch.object(client.http_client, 'request') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            await client._create_topic("test-topic", "Test description")
            mock_post.assert_called_once_with(
                "post",
                "http://localhost:8008/api/v1/topics",
                json={
                    "topic_id": "test-topic",
                    "name": "test-topic",
                    "description": "Test description"
                },
                timeout=30,
            )
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, client):
        """测试创建subscription"""
        with patch.object(client.http_client, 'request') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            await client._create_subscription("test-topic", "http://example.com/webhook")
            
            mock_post.assert_called_once_with(
                "post",
                "http://localhost:8008/api/v1/topics/test-topic/subscriptions",
                json={
                    "url": "http://example.com/webhook",
                    "secret": client.webhook_secret,
                    "headers": {},
                    "enabled": True
                },
                timeout=30,
            )
    
    @pytest.mark.asyncio
    async def test_run_plugin(self, client):
        """测试运行插件"""
        with patch.object(client.http_client, 'request') as mock_post:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            config = {"param1": "value1"}
            await client._run_plugin("test-plugin", config, "test-topic")
            
            mock_post.assert_called_once_with(
                "post",
                "http://localhost:8008/api/v1/tasks",
                json={
                    "plugin_id": "test-plugin",
                    "run_mode": "once",
                    "config": config,
                    "topic_id": "test-topic"
                },
                timeout=30,
            )
    
    @pytest.mark.asyncio
    async def test_rpc_call_context_manager(self, client):
        """测试RPC调用上下文管理器"""
        with patch.object(client, '_create_topic') as mock_create_topic, \
             patch.object(client, '_create_subscription') as mock_create_sub, \
             patch.object(client, '_run_plugin') as mock_run_plugin:
            
            # 模拟成功的调用
            config = {"test": "config"}
            
            # 创建一个已完成的Future来模拟成功响应
            future = asyncio.Future()
            future.set_result({"success": True, "data": "test result"})
            
            with patch('asyncio.Future', return_value=future):
                async with client._rpc_call("test-plugin", config) as result:
                    assert result == {"success": True, "data": "test result"}
            
            # 验证调用
            mock_create_topic.assert_called_once()
            mock_create_sub.assert_called_once()
            mock_run_plugin.assert_called_once_with("test-plugin", config, mock_create_topic.call_args[0][0])


class TestEAIRPCClientSync:
    """测试同步RPC客户端"""
    
    def test_sync_client_initialization(self):
        """测试同步客户端初始化"""
        client = EAIRPCClientSync(
            base_url="http://localhost:8008",
            api_key="testkey"
        )
        
        assert client._client.base_url == "http://localhost:8008"
        assert client._client.api_key == "testkey"
        assert client._loop is None
    
    def test_ensure_loop(self):
        """测试事件循环确保"""
        client = EAIRPCClientSync("http://localhost:8008", "testkey")
        
        assert client._loop is None
        client._ensure_loop()
        assert client._loop is not None
        assert isinstance(client._loop, asyncio.AbstractEventLoop)


@pytest.mark.integration
class TestRPCClientIntegration:
    """集成测试（需要运行的EAI服务器）"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整的工作流程"""
        # 这个测试需要实际运行的EAI服务器
        # 在CI/CD中可以跳过或使用mock服务器
        
        client = EAIRPCClient(
            base_url="http://localhost:8008",
            api_key="testkey",
            webhook_port=9998  # 使用不同端口避免冲突
        )
        
        try:
            # 这里可以添加实际的集成测试
            # 但需要确保有运行的EAI服务器
            pass
        except Exception as e:
            # 如果服务器未运行，跳过测试
            pytest.skip(f"EAI server not available: {e}")
        finally:
            await client.stop()


class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """测试超时处理"""
        client = EAIRPCClient("http://localhost:8008", "testkey")
        
        # 模拟超时情况
        with patch.object(client, '_create_topic'), \
             patch.object(client, '_create_subscription'), \
             patch.object(client, '_run_plugin'):
            
            with pytest.raises(TimeoutError):
                async with client._rpc_call("test-plugin", {}, timeout=0.1):
                    await asyncio.sleep(0.2)  # 超过超时时间
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """测试HTTP错误处理"""
        client = EAIRPCClient("http://localhost:8008", "testkey")
        
        with patch.object(client.http_client, 'request') as mock_post:
            # 模拟HTTP错误
            import httpx
            mock_post.side_effect = httpx.HTTPStatusError(
                "HTTP Error", request=None, response=None
            )
            
            with pytest.raises(httpx.HTTPStatusError):
                await client._create_topic("test-topic", "description")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])