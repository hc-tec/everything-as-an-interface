#!/usr/bin/env python3
"""
万物皆接口 - 命令行入口
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any

from src.core.task_config import TaskConfig

from . import EverythingAsInterface, __version__
from .core.orchestrator import Orchestrator

def setup_logging(level: str) -> None:
    """
    设置日志级别
    
    Args:
        level: 日志级别
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"无效的日志级别: {level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("everything-as-an-interface.log")
        ]
    )

async def run_plugin(args: argparse.Namespace) -> None:
    """
    运行单个插件
    
    Args:
        args: 命令行参数
    """
    system = EverythingAsInterface()

    # 加载配置
    config: TaskConfig = {}
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return

    # 准备 Cookie（如需要）
    cookie_items = None
    if getattr(args, "cookies", None):
        try:
            cookie_ids = [c for c in args.cookies.split(",") if c]
            cookie_items = system.account_manager.merge_cookies(cookie_ids)
        except Exception as e:
            print(f"处理 Cookie 参数失败: {str(e)}")
            return

    # 启动编排器并分配上下文
    orch = Orchestrator()
    await orch.start(headless=config.get("headless", False))
    ctx = await orch.allocate_context_page(
        cookie_items=cookie_items,
        settings={"plugin": args.plugin_id},
        account_manager=system.account_manager,
    )

    # 创建插件实例（注册表）
    try:
        plugin = system.plugin_manager.instantiate_plugin(args.plugin_id, ctx, config)
    except ValueError as e:
        await orch.release_context_page(ctx)
        await orch.stop()
        print(str(e))
        return

    # 输入参数
    input_payload: Dict[str, Any] = {}
    if getattr(args, "text", None):
        input_payload["text"] = args.text
    if getattr(args, "link", None):
        input_payload["link"] = args.link
    if getattr(args, "image", None):
        input_payload["image"] = args.image
    if input_payload:
        plugin.set_input(input_payload)

    print(f"正在运行插件: {args.plugin_id}")
    plugin.start()
    try:
        result = await plugin.fetch()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"结果已保存至: {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"插件执行失败: {str(e)}")
    finally:
        plugin.stop()
        await orch.release_context_page(ctx)
        await orch.stop()

async def run_server(args: argparse.Namespace) -> None:
    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        print("错误: 需要安装FastAPI和uvicorn才能运行API服务器")
        print("请执行: pip install fastapi uvicorn")
        return
    
    print(f"API服务器功能尚未实现，将在未来版本中提供")
    # TODO: 实现API服务器

def list_plugins(args: argparse.Namespace) -> None:
    system = EverythingAsInterface()
    plugins = system.plugin_manager.get_all_plugins()
    if not plugins:
        print("没有可用的插件")
        return
    print(f"可用插件 ({len(plugins)}):")
    print("-" * 60)
    for plugin_id in plugins.keys():
        print(f"插件ID: {plugin_id}")
    print("-" * 60)

def manage_sessions(args: argparse.Namespace) -> None:
    system = EverythingAsInterface()
    if args.action == "list":
        items = system.account_manager.list_cookies(args.platform) if args.platform else system.account_manager.list_cookies()
        if not items:
            print("没有保存的 Cookie")
            return
        print(f"Cookie 列表 ({len(items)}):")
        print("-" * 60)
        for item in items:
            print(f"ID: {item['id']}")
            print(f"平台: {item['platform_name']} ({item['platform_id']})")
            print(f"名称: {item['name']}")
            print(f"状态: {item.get('status', 'valid')}")
            if item.get('detected_accounts'):
                print(f"检测账号: {item['detected_accounts']}")
            print("-" * 60)
    elif args.action == "remove":
        if not args.id:
            print("错误: 删除 Cookie 时需要指定 ID")
            return
        success = system.account_manager.remove_cookie(args.id)
        print(f"Cookie {args.id} {'已删除' if success else '不存在或删除失败'}")
    elif args.action == "prune":
        removed = system.account_manager.prune_expired_cookies()
        print(f"已清理过期 Cookie 数量: {removed}")
    else:
        print(f"错误: 未知的 Cookie 操作 '{args.action}'")

def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="万物皆接口 - 将各种网站和应用转换为可编程接口")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error", "critical"], 
                       default="info", help="设置日志级别")
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 运行插件命令
    run_parser = subparsers.add_parser("run", help="运行单个插件")
    run_parser.add_argument("plugin_id", help="插件ID")
    run_parser.add_argument("--config", help="配置文件路径")
    run_parser.add_argument("--cookies", help="以逗号分隔的 cookie_id 列表")
    run_parser.add_argument("--output", help="输出文件路径")
    run_parser.add_argument("--text", help="传递给插件的文本输入")
    run_parser.add_argument("--link", help="传递给插件的链接输入")
    run_parser.add_argument("--image", help="传递给插件的图片输入（本地路径或URL）")
    
    # 服务器命令
    server_parser = subparsers.add_parser("server", help="运行API服务器")
    server_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    server_parser.add_argument("--port", type=int, default=8000, help="监听端口")
    
    # 列出插件命令
    list_parser = subparsers.add_parser("list", help="列出可用的插件")
    
    # Cookie 管理命令
    session_parser = subparsers.add_parser("cookies", help="管理 Cookie")
    session_parser.add_argument("action", choices=["list", "remove", "prune"], help="Cookie 操作")
    session_parser.add_argument("--platform", help="平台ID (筛选时使用)")
    session_parser.add_argument("--id", help="Cookie ID (删除时使用)")

    args = parser.parse_args()
    setup_logging(args.log_level)
    
    if args.command == "run":
        asyncio.run(run_plugin(args))
    elif args.command == "server":
        asyncio.run(run_server(args))
    elif args.command == "list":
        list_plugins(args)
    elif args.command == "cookies":
        manage_sessions(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 