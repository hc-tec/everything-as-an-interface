#!/usr/bin/env python3
"""
万物皆接口 - 示例程序（注入式上下文 + 调度订阅）
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any

from src import EverythingAsInterface
from src.core.orchestrator import Orchestrator
from src.core.task_config import TaskConfig
from src.plugins.xiaohongshu_v2 import XiaohongshuV2Plugin

async def on_new_favorite(data: Dict[str, Any]) -> None:
    """
    新收藏处理回调函数
    
    Args:
        data: 收藏夹数据
    """
    print("\n" + "="*50)
    print(f"检测到 {len(data['new_items'])} 条新收藏:")
    for idx, item in enumerate(data['new_items'], 1):
        print(f"\n{idx}. {item['title']}")
    print("="*50 + "\n")

async def main():
    logging.basicConfig(level=logging.DEBUG)
    os.makedirs("accounts", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    # 初始化系统
    system = EverythingAsInterface(config={
        "master_key": "your-secret-key",  # 生产环境应使用安全的密钥存储方案
        "accounts_path": "./accounts"
    })

    # 核心信息打印
    print("系统已初始化")
    try:
        # 新的注册制下，插件列表通过 PluginManager.get_all_plugins()
        plugin_ids = list(system.plugin_manager.get_all_plugins().keys())
    except Exception:
        plugin_ids = []
    print(f"已加载的插件: {plugin_ids}")
    print("注意：首次使用将手动登录以保存 Cookie；后续运行可配置 cookie_ids 直接复用")

    # 创建收藏夹监听主题
    topic_id = system.subscription_system.create_topic(
        name="小红书收藏夹更新",
        description="监听小红书收藏夹的变化"
    )
    print(f"已创建主题: {topic_id}")

    # 订阅主题
    subscriber_id = system.subscription_system.subscribe(
        topic_id=topic_id,
        callback=on_new_favorite
    )
    print(f"已创建订阅: {subscriber_id}")

    # 添加任务（使用调度器）
    task_id = system.scheduler.add_task(
        plugin_id="xiaohongshu_v2",
        interval=300,  # 5分钟检查一次
        config=TaskConfig(
            # 可选：填写已保存的 cookie_ids 列表，以跳过手动登录
            cookie_ids=["3d1ab44f-71ea-48eb-96c7-5dca21cc7987"],
            extra={
                "video_output_dir": "videos_data",
                "task_type": "favorites",
                "note_ids": ["64a54a7d0000000023036647?xsec_token=ABAGtrrS0w5pLKIte2XwU4DKg4UIJJkWOdWz14wWBL3FE=&xsec_source=pc_feed"]
            }
        )
    )
    print(f"已添加任务: {task_id}")

    # 任务完成回调：发布到主题
    async def task_callback(result: Dict[str, Any]) -> None:
        if result.get("success"):
            await system.subscription_system.publish(topic_id, result)
        elif result.get("need_relogin"):
            print("检测到需要重新登录，请在浏览器中登录以刷新 Cookie")

    system.scheduler.tasks[task_id].callback = task_callback

    # 使用 Orchestrator（外部创建并注入到调度器）
    orchestrator = Orchestrator()
    await orchestrator.start(headless=False)
    system.scheduler.set_orchestrator(orchestrator)

    # 启动调度器
    await system.scheduler.start()
    print("调度器已启动，按Ctrl+C停止")
    print("首次运行时会打开浏览器要求手动登录")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("正在停止...")
    finally:
        await system.scheduler.stop()
        await orchestrator.stop()
        print("已停止")

if __name__ == "__main__":
    asyncio.run(main()) 
