"""Tests for NetRuleBus task management and cleanup mechanisms."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.net_rule_bus import NetRuleBus, Subscription, MergedEvent
from src.utils.net_rules import ResponseView, RequestView


class TestNetRuleBusTaskManagement:
    """Test NetRuleBus task management features."""

    @pytest.fixture
    def bus(self):
        """Create a NetRuleBus instance for testing."""
        return NetRuleBus(max_queue_size=10, task_timeout=1.0)

    @pytest.fixture
    def mock_page(self):
        """Create a mock page object."""
        page = MagicMock()
        page.on = MagicMock()
        page.off = MagicMock()
        return page

    def test_initialization_with_parameters(self):
        """Test NetRuleBus initialization with custom parameters."""
        bus = NetRuleBus(max_queue_size=500, task_timeout=60.0)
        assert bus._max_queue_size == 500
        assert bus._task_timeout == 60.0
        assert bus._cleanup_interval == 60.0
        assert hasattr(NetRuleBus, '_instances')
        assert bus in NetRuleBus._instances

    def test_subscription_with_queue_size_limit(self, bus):
        """Test that subscriptions create queues with size limits."""
        queue = bus.subscribe("test_pattern")
        assert queue.maxsize == 10

    @pytest.mark.asyncio
    async def test_bind_starts_cleanup_task(self, bus, mock_page):
        """Test that binding starts the cleanup task."""
        with patch.object(bus, '_start_cleanup_task', new_callable=AsyncMock) as mock_start:
            await bus.bind(mock_page)
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_unbind_stops_cleanup_task(self, bus, mock_page):
        """Test that unbinding stops the cleanup task."""
        # Mock cleanup task
        cleanup_task = MagicMock()
        cleanup_task.done.return_value = False
        cleanup_task.cancel = MagicMock()
        bus._cleanup_task = cleanup_task

        unbind = await bus.bind(mock_page)
        unbind()
        
        cleanup_task.cancel.assert_called_once()

    def test_get_resource_stats(self, bus):
        """Test resource statistics collection."""
        # Add some subscriptions
        bus.subscribe("pattern1")
        bus.subscribe("pattern2", kind="request")
        
        stats = bus.get_resource_stats()
        
        assert 'active_tasks' in stats
        assert 'total_subscriptions' in stats
        assert 'bound' in stats
        assert 'queue_stats' in stats
        assert 'cleanup_task_running' in stats
        
        assert stats['total_subscriptions'] == 2
        assert len(stats['queue_stats']) == 2
        assert stats['bound'] is False

    @pytest.mark.asyncio
    async def test_subscribe_many_with_queue_limits(self, bus):
        """Test subscribe_many creates queues with proper limits."""
        patterns = [
            ("pattern1", "response"),
            ("pattern2", "request"),
            "pattern3"
        ]
        
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        # Check that all subscriptions have proper queue limits
        for sub in bus._subs:
            assert sub.queue.maxsize == 10
        
        assert len(id_to_meta) == 3
        assert len(bus._forward_tasks) == 3

    @pytest.mark.asyncio
    async def test_forward_task_timeout_handling(self, bus):
        """Test that forward tasks handle timeouts properly."""
        patterns = [("test_pattern", "response")]
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        # Wait a bit to let the forward task start
        await asyncio.sleep(0.1)
        
        # The forward task should be running
        assert len(bus._forward_tasks) == 1
        
        # Clean up
        bus.cleanup_all_tasks()

    @pytest.mark.asyncio
    async def test_unsubscribe_many_by_ids(self, bus):
        """Test unsubscribing multiple subscriptions by IDs."""
        patterns = [("pattern1", "response"), ("pattern2", "request")]
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        initial_count = len(bus._subs)
        ids_to_remove = list(id_to_meta.keys())[:1]
        
        bus.unsubscribe_many_by_ids(ids_to_remove)
        
        assert len(bus._subs) == initial_count - 1
        assert len(bus._forward_tasks) == initial_count - 1

    @pytest.mark.asyncio
    async def test_cleanup_all_tasks(self, bus):
        """Test cleaning up all tasks."""
        patterns = [("pattern1", "response"), ("pattern2", "request")]
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        assert len(bus._forward_tasks) > 0
        
        bus.cleanup_all_tasks()
        
        assert len(bus._forward_tasks) == 0
        assert len(bus._subs_with_ids) == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_subscriptions(self, bus):
        """Test cleanup of stale subscriptions."""
        # Create a subscription and make it stale
        patterns = [("test_pattern", "response")]
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        # Make the subscription stale by setting old last_activity
        sub_id = list(id_to_meta.keys())[0]
        bus._subs_with_ids[sub_id].last_activity = time.time() - 7200  # 2 hours ago
        
        initial_count = len(bus._subs)
        await bus._cleanup_stale_subscriptions()
        
        # Should have removed the stale subscription
        assert len(bus._subs) < initial_count

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self, bus):
        """Test cleanup of completed tasks."""
        # Create some tasks
        patterns = [("pattern1", "response"), ("pattern2", "request")]
        merged_queue, id_to_meta = bus.subscribe_many(patterns)
        
        # Mock one task as completed
        task_id = list(bus._forward_tasks.keys())[0]
        bus._forward_tasks[task_id].done = MagicMock(return_value=True)
        
        initial_count = len(bus._forward_tasks)
        await bus._cleanup_completed_tasks()
        
        # Should have removed the completed task
        assert len(bus._forward_tasks) < initial_count

    @pytest.mark.asyncio
    async def test_cleanup_all_instances(self):
        """Test class method for cleaning up all instances."""
        # Create multiple instances
        bus1 = NetRuleBus()
        bus2 = NetRuleBus()
        
        # Add some tasks
        patterns = [("pattern1", "response")]
        bus1.subscribe_many(patterns)
        bus2.subscribe_many(patterns)
        
        # Clean up all instances
        NetRuleBus.cleanup_all_instances()
        
        # All tasks should be cleaned up
        assert len(bus1._forward_tasks) == 0
        assert len(bus2._forward_tasks) == 0


class TestNetRuleBusErrorHandling:
    """Test NetRuleBus error handling improvements."""

    @pytest.fixture
    def bus(self):
        """Create a NetRuleBus instance for testing."""
        return NetRuleBus(max_queue_size=2)  # Small queue for testing overflow

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        req = MagicMock()
        req.url = "https://example.com/test"
        req.method = "GET"
        req.headers = {"Content-Type": "application/json"}
        req.post_data = AsyncMock(return_value=None)
        req.post_data_json = AsyncMock(return_value=None)
        return req

    @pytest.fixture
    def mock_response(self):
        """Create a mock response object."""
        resp = MagicMock()
        resp.url = "https://example.com/test"
        resp.json = AsyncMock(return_value={"data": "test"})
        resp.text = AsyncMock(return_value="test")
        resp.body = AsyncMock(return_value=b"test")
        return resp

    @pytest.mark.asyncio
    async def test_queue_overflow_handling_request(self, bus, mock_request):
        """Test queue overflow handling for requests."""
        # Subscribe to requests
        queue = bus.subscribe("example.com", kind="request")
        
        # Fill the queue to capacity
        for _ in range(3):  # More than max_queue_size
            await bus._on_request(mock_request)
        
        # Queue should not exceed its limit
        assert queue.qsize() <= bus._max_queue_size

    @pytest.mark.asyncio
    async def test_queue_overflow_handling_response(self, bus, mock_response):
        """Test queue overflow handling for responses."""
        # Subscribe to responses
        queue = bus.subscribe("example.com", kind="response")
        
        # Fill the queue to capacity
        for _ in range(3):  # More than max_queue_size
            await bus._on_response(mock_response)
        
        # Queue should not exceed its limit
        assert queue.qsize() <= bus._max_queue_size

    @pytest.mark.asyncio
    async def test_error_handling_in_request_processing(self, bus):
        """Test error handling when processing requests."""
        # Subscribe to requests
        bus.subscribe("example.com", kind="request")
        
        # Create a request that will cause an error
        bad_request = MagicMock()
        bad_request.url = "https://example.com/test"
        bad_request.method = None  # This might cause an error
        bad_request.headers = None
        
        # Should not raise an exception
        await bus._on_request(bad_request)

    @pytest.mark.asyncio
    async def test_error_handling_in_response_processing(self, bus):
        """Test error handling when processing responses."""
        # Subscribe to responses
        bus.subscribe("example.com", kind="response")
        
        # Create a response that will cause an error
        bad_response = MagicMock()
        bad_response.url = "https://example.com/test"
        bad_response.json = AsyncMock(side_effect=Exception("JSON error"))
        bad_response.text = AsyncMock(side_effect=Exception("Text error"))
        bad_response.body = AsyncMock(side_effect=Exception("Body error"))
        
        # Should not raise an exception
        await bus._on_response(bad_response)

    @pytest.mark.asyncio
    async def test_delegate_error_handling(self, bus, mock_response):
        """Test error handling in delegate callbacks."""
        # Set up a delegate that raises an error
        bus._delegate.on_response = AsyncMock(side_effect=Exception("Delegate error"))
        
        # Subscribe to responses
        bus.subscribe("example.com", kind="response")
        
        # Should not raise an exception even if delegate fails
        await bus._on_response(mock_response)