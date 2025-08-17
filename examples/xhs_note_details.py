#!/usr/bin/env python3
"""
万物皆接口 - 示例程序（注入式上下文 + 调度订阅）
"""

import sys
import signal
import asyncio
import json
import logging
import os
from typing import Dict, Any

from settings import PROJECT_ROOT
from src import EverythingAsInterface
from src.core.orchestrator import Orchestrator
from src.core.task_config import TaskConfig
from src.plugins.xiaohongshu_details import XiaohongshuNoteDetailPlugin


async def on_new_favorite(data: Dict[str, Any]) -> None:
    """
    新收藏处理回调函数

    Args:
        data: { **收藏夹数据, "task_config_extra": 任务配置额外参数 }
    """
    try:
        print("\n" + "="*50)
        print(f"检测到 {len(data['data'])} 条新收藏:")
        for idx, item in enumerate(data['data'], 1):
            print(f"\n{idx}. {item['title']}")
        print("="*50 + "\n")
        search_words = data["task_config_extra"]["search_words"]
        with open(os.path.join(PROJECT_ROOT, f"data/note-details-search-{search_words}.json"), "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"on_new_favorite, {e}")

async def main():
    os.makedirs("../accounts", exist_ok=True)
    os.makedirs("../data", exist_ok=True)
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
        plugin_id="xiaohongshu_details",
        interval=1000000,  # 10分钟检查一次
        config=TaskConfig(
            # 可选：填写已保存的 cookie_ids 列表，以跳过手动登录
            cookie_ids=["12e12361-b5e3-41ec-ac9e-ef29b675bdb4"],
            extra={
                "search_words": "摄影",
                "diff_file": "data/note-search-摄影.json",
                "failed_file": "data/failed_notes.json",
                # NoteNetCollectionConfig
                "max_items": 50,
                "max_idle_rounds": 999,
                "max_seconds": 99999,
                # PassiveSyncEngine Config
                "deletion_policy": "soft",
                "stop_after_consecutive_known": 5,
                "stop_after_no_change_batches": 2,
                "stop_max_items": 50,
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

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    # 跨平台信号桥接：非 Windows 用 add_signal_handler；Windows 用 signal.signal + call_soon_threadsafe
    if sys.platform == "win32":
        def _win_sig_handler(signum, frame):
            # 在信号处理器里不能直接触碰 asyncio 对象，用线程安全的方式投递回事件循环
            loop.call_soon_threadsafe(stop_event.set)
        # Ctrl+C
        signal.signal(signal.SIGINT, _win_sig_handler)
        # Ctrl+Break（有的终端可用）
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _win_sig_handler)
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()

    print("正在停止...")
    await system.scheduler.stop()
    await orchestrator.stop()
    print("已停止")

if __name__ == "__main__":
    asyncio.run(main()) 
