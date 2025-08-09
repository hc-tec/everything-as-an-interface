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

from . import EverythingAsInterface, __version__

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
    # 初始化系统
    system = EverythingAsInterface()
    
    # 检查插件是否存在
    if args.plugin_id not in system.plugin_manager.plugins:
        available_plugins = list(system.plugin_manager.plugins.keys())
        print(f"错误: 插件 '{args.plugin_id}' 不存在")
        print(f"可用插件: {', '.join(available_plugins)}")
        return
    
    # 加载配置
    config = {}
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return
    
    # 实例化插件
    plugin = system.plugin_manager.instantiate_plugin(args.plugin_id)
    plugin.configure(config)

    # 基于 Cookie 的账号管理：支持通过 --cookies 传入多个 cookie_id
    if plugin.needs_account() and getattr(args, "cookies", None):
        try:
            cookie_ids = [c for c in args.cookies.split(",") if c]
            plugin.configure({**config, "cookie_ids": cookie_ids})
            setattr(plugin, "account_manager", system.account_manager)
        except Exception as e:
            print(f"处理 Cookie 参数失败: {str(e)}")
            return
    
    # 设置输入参数
    input_payload: Dict[str, Any] = {}
    if getattr(args, "text", None):
        input_payload["text"] = args.text
    if getattr(args, "link", None):
        input_payload["link"] = args.link
    if getattr(args, "image", None):
        input_payload["image"] = args.image
    if input_payload:
        plugin.set_input(input_payload)

    # 启动插件
    print(f"正在运行插件: {args.plugin_id}")
    plugin.start()
    
    try:
        # 获取数据
        result = await plugin.fetch()
        
        # 输出结果
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"结果已保存至: {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"插件执行失败: {str(e)}")
    finally:
        # 停止插件
        plugin.stop()

async def run_server(args: argparse.Namespace) -> None:
    """
    运行API服务器
    
    Args:
        args: 命令行参数
    """
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
    """
    列出可用的插件
    
    Args:
        args: 命令行参数
    """
    # 初始化系统
    system = EverythingAsInterface()
    plugins = system.plugin_manager.get_all_plugins()
    
    if not plugins:
        print("没有可用的插件")
        return
    
    # 显示插件列表
    print(f"可用插件 ({len(plugins)}):")
    print("-" * 60)
    
    for plugin_id, plugin_class in plugins.items():
        print(f"插件ID: {plugin_id}")
        print(f"名称: {plugin_class.PLUGIN_NAME}")
        print(f"描述: {plugin_class.PLUGIN_DESCRIPTION}")
        print(f"版本: {plugin_class.PLUGIN_VERSION}")
        print(f"作者: {plugin_class.PLUGIN_AUTHOR}")
        print("-" * 60)

def manage_sessions(args: argparse.Namespace) -> None:
    """管理 Cookie 存储"""
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
        if success:
            print(f"Cookie {args.id} 已删除")
        else:
            print(f"Cookie {args.id} 不存在或删除失败")
    
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