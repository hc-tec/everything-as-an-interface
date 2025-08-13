#!/usr/bin/env python3
"""
Example demonstrating how to use Xiaohongshu site services.

This example shows how to:
1. Use NoteService to collect favorite items
2. Use DetailService to get detailed information about specific notes
3. Use CommentService to fetch comments
4. Use SearchService to search for content
5. Use PublishService to publish new content

Run this example:
    python examples/xiaohongshu_services_example.py
"""

import asyncio
import logging

from src.core.orchestrator import Orchestrator
from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig
from src.services.base import NoteCollectArgs, PublishContent
from src.services.xiaohongshu import (
    XiaohongshuCommentService,
    XiaohongshuDetailService,
    XiaohongshuNoteNetService,
)
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_feed_service():
    """Demonstrate using NoteService to collect favorites."""
    logger.info("=== Feed Service Demo ===")
    
    # Setup
    orchestrator = Orchestrator()

    ctx = PluginContext(
        orchestrator=orchestrator,
        page=orchestrator.page,
        config=TaskConfig()
    )
    
    # Create and attach feed service
    feed_service = XiaohongshuNoteNetService()
    await feed_service.attach(ctx.page)
    
    # Configure collection settings
    feed_config = NoteNetCollectionConfig(
        max_items=10,
        max_seconds=30,
        auto_scroll=True
    )
    feed_service.configure(feed_config)
    
    # Set custom stop condition (optional)
    def stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra, last_view):
        # Stop if we find any item with "旅行" tag
        for item in last_batch:
            if "旅行" in (getattr(item, "tags", []) or []):
                logger.info("Found travel-related content, stopping collection")
                return True
        return False
    
    feed_service.set_stop_decider(stop_decider)
    
    # Collect favorites
    async def goto_favorites():
        # Navigate to favorites page
        await ctx.page.goto("https://www.xiaohongshu.com/user/profile/favorites")
        await asyncio.sleep(2)
    
    try:
        items = await feed_service.collect(NoteCollectArgs(
            goto_first=goto_favorites,
            extra_config={"custom_param": "demo"}
        ))
        
        logger.info(f"Collected {len(items)} favorite items")
        for i, item in enumerate(items[:3]):  # Show first 3
            logger.info(f"Item {i+1}: {getattr(item, 'title', 'No title')}")
            
    except Exception as e:
        logger.error(f"Feed collection failed: {e}")
    
    await feed_service.detach()
    await orchestrator.cleanup()


async def demo_detail_service():
    """Demonstrate using DetailService to get note details."""
    logger.info("=== Detail Service Demo ===")
    
    # Setup
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Create and attach detail service
    detail_service = XiaohongshuDetailService()
    await detail_service.attach(orchestrator.page)
    
    # Example note IDs (replace with real ones)
    note_ids = ["64a1b2c3d4e5f", "64b2c3d4e5f6a", "64c3d4e5f6a7b"]
    
    try:
        # Get single detail
        detail_args = DetailArgs(
            item_id=note_ids[0],
            extra_config={"timeout": 15.0}
        )
        detail = await detail_service.get_detail(detail_args)
        
        if detail:
            logger.info(f"Got detail for note: {detail.title}")
            logger.info(f"Author: {detail.author.username}")
            logger.info(f"Like count: {detail.like_count}")
        else:
            logger.info("No detail found")
        
        # Get batch details
        details = await detail_service.get_details_batch(
            note_ids,
            extra_config={"delay_ms": 1000}
        )
        
        successful_details = [d for d in details if d is not None]
        logger.info(f"Got {len(successful_details)} details out of {len(note_ids)} requested")
        
    except Exception as e:
        logger.error(f"Detail fetching failed: {e}")
    
    await detail_service.detach()
    await orchestrator.cleanup()


async def demo_comment_service():
    """Demonstrate using CommentService to get comments."""
    logger.info("=== Comment Service Demo ===")
    
    # Setup
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Create and attach comment service
    comment_service = XiaohongshuCommentService()
    await comment_service.attach(orchestrator.page)
    
    # Example note ID
    note_id = "64a1b2c3d4e5f"
    
    try:
        comments = await comment_service.collect_for_note(
            note_id,
            max_pages=3,
            delay_ms=500
        )
        
        logger.info(f"Got {len(comments)} comments for note {note_id}")
        for i, comment in enumerate(comments[:3]):  # Show first 3
            logger.info(f"Comment {i+1} by {comment.author.username}: {comment.content[:50]}...")
            
    except Exception as e:
        logger.error(f"Comment fetching failed: {e}")
    
    await comment_service.detach()
    await orchestrator.cleanup()


async def demo_search_service():
    """Demonstrate using SearchService to search content."""
    logger.info("=== Search Service Demo ===")
    
    # Setup
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Create and attach search service
    search_service = XiaohongshuSearchService()
    await search_service.attach(orchestrator.page)
    
    try:
        results = await search_service.search(
            "旅行攻略",
            max_batches=3,
            delay_ms=800
        )
        
        logger.info(f"Found {len(results)} search results")
        for i, result in enumerate(results[:3]):  # Show first 3
            logger.info(f"Result {i+1}: {result.title}")
            logger.info(f"Author: {result.author.username}")
            logger.info(f"Tags: {', '.join(result.tags)}")
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
    
    await search_service.detach()
    await orchestrator.cleanup()


async def demo_publish_service():
    """Demonstrate using PublishService to publish content."""
    logger.info("=== Publish Service Demo ===")
    
    # Setup
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # Create and attach publish service
    publish_service = XiaohongshuPublishService()
    await publish_service.attach(orchestrator.page)
    
    # Prepare content to publish
    content = PublishContent(
        title="自动化发布测试",
        content="这是一个使用自动化工具发布的测试内容。包含一些有趣的描述和标签。",
        tags=["自动化", "测试", "工具"],
        visibility="private",  # Use private for testing
        extra_config={
            "comment_enabled": True,
            "location_enabled": False,
            "original_declaration": True
        }
    )
    
    try:
        # Save as draft first (safer for testing)
        draft_result = await publish_service.save_draft(content)
        
        if draft_result.success:
            logger.info("Successfully saved as draft")
            logger.info(f"Draft ID: {draft_result.item_id}")
        else:
            logger.error(f"Draft save failed: {draft_result.error_message}")
        
        # For actual publishing (uncomment to test):
        # publish_result = await publish_service.publish(content)
        # if publish_result.success:
        #     logger.info(f"Successfully published: {publish_result.url}")
        #     
        #     # Check status
        #     status = await publish_service.get_publish_status(publish_result.item_id)
        #     logger.info(f"Publish status: {status}")
        # else:
        #     logger.error(f"Publish failed: {publish_result.error_message}")
            
    except Exception as e:
        logger.error(f"Publishing failed: {e}")
    
    await publish_service.detach()
    await orchestrator.cleanup()


async def main():
    """Run all service demos."""
    logger.info("Starting Xiaohongshu Services Demo")
    
    demos = [
        demo_feed_service,
        demo_detail_service,
        demo_comment_service,
        demo_search_service,
        demo_publish_service,
    ]
    
    for demo in demos:
        try:
            await demo()
            await asyncio.sleep(2)  # Pause between demos
        except Exception as e:
            logger.error(f"Demo {demo.__name__} failed: {e}")
    
    logger.info("All demos completed")


if __name__ == "__main__":
    asyncio.run(main())
