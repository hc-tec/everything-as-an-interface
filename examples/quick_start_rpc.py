#!/usr/bin/env python3
"""
快速开始 - RPC客户端

最简单的使用方式，只需几行代码即可调用插件功能。
"""

import asyncio
from src.client.rpc_client import EAIRPCClient, EAIRPCClientSync, logger


async def main():
    # 创建客户端
    client = EAIRPCClient(
        base_url="http://127.0.0.1:8008",
        api_key="testkey",  # 替换为你的API密钥
        webhook_host="127.0.0.1",
        webhook_port=9002,
    )
    
    try:
        # 启动客户端
        await client.start()
        print("✅ RPC客户端已启动")
        
        # 🤖 与AI聊天
        print("\n🤖 与AI元宝聊天...")
        chat_result = await client.chat_with_yuanbao(
            message="你好，今天天气怎么样？",
            cookie_ids=["819969a2-9e59-46f5-b0ca-df2116d9c2a0"]
        )
        print(f"AI回复: {chat_result.get('data', 'N/A')}")
        
        # # 📱 获取小红书笔记
        # print("\n📱 获取小红书美食笔记...")
        # notes = await client.get_notes_brief_from_xhs(
        #     keywords=["美食", "推荐"],
        #     max_items=5
        # )
        # print(f"获取到 {len(notes.get('items', []))} 条笔记")
        #
        # # 打印前3条笔记标题
        # for i, note in enumerate(notes.get('items', [])[:3]):
        #     print(f"  {i+1}. {note.get('title', 'N/A')}")
        #
        # # 🔍 搜索小红书内容
        # print("\n🔍 搜索小红书咖啡内容...")
        # search_result = await client.search_notes_from_xhs(
        #     keywords=["咖啡", "拿铁"],
        #     max_items=3
        # )
        # print(f"搜索到 {len(search_result.get('items', []))} 条相关内容")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    finally:
        # 停止客户端
        await client.stop()
        print("\n✅ RPC客户端已停止")


if __name__ == "__main__":
    print("🚀 启动RPC客户端快速示例...")
    try:
        asyncio.run(main())
    except asyncio.CancelledError as e:
        pass
    