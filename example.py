#!/usr/bin/env python3
"""
万物皆接口 - 示例程序

演示如何使用系统的核心功能，实现小红书收藏夹监听
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any

from src import EverythingAsInterface

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
        print(f"   作者: {item['author']}")
        print(f"   链接: {item['link']}")
        print(f"   时间: {item['timestamp']}")
    
    print("="*50 + "\n")

async def main():
    """主函数"""
    # 创建配置目录
    os.makedirs("accounts", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # 初始化系统
    system = EverythingAsInterface(config={
        "master_key": "your-secret-key",  # 生产环境应使用安全的密钥存储方案
        "accounts_path": "./accounts"
    })
    
    print("系统已初始化")
    print(f"已加载的插件: {list(system.plugin_manager.plugins.keys())}")
    
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
    
    # 添加任务
    task_id = system.scheduler.add_task(
        plugin_id="xiaohongshu",
        interval=300,  # 5分钟检查一次
        config={
            # 可选：填写已保存的 cookie_ids 列表，以跳过手动登录
            "cookie_ids": ["1f2a15fd-5027-43ab-ba84-b82785cc6b08"],
            "headless": False,  # 首次登录时建议可视化
        }
    )
    
    print(f"已添加任务: {task_id}")
    
    # 设置任务完成后的回调，将结果发布到主题
    async def task_callback(result: Dict[str, Any]) -> None:
        if result.get("success"):
            await system.subscription_system.publish(topic_id, result)
        elif result.get("need_relogin"):
            print("检测到需要重新登录，请在浏览器中登录以刷新 Cookie")
    
    # 更新任务配置，添加回调
    system.scheduler.tasks[task_id].callback = task_callback
    
    # 启动调度器
    await system.scheduler.start()
    print("调度器已启动，按Ctrl+C停止")
    print("首次运行时会打开浏览器要求手动登录")
    
    try:
        # 保持运行直到手动中断
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("正在停止...")
    finally:
        # 停止调度器
        await system.scheduler.stop()
        print("已停止")

if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    
    # 运行主函数
    asyncio.run(main()) 