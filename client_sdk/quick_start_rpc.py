#!/usr/bin/env python3
"""
快速开始 - RPC客户端

最简单的使用方式，只需几行代码即可调用插件功能。
"""

import asyncio

from client_sdk.rpc_client import EAIRPCClient


async def main():
    # 创建客户端
    client = EAIRPCClient(
        base_url="http://127.0.0.1:8008", # 服务程序ip+port
        api_key="testkey",  # 与服务程序约定好的API密钥
        webhook_host="127.0.0.1", # webhook订阅服务，当服务程序成功获取到client所需要的订阅数据时，就会通过webhook调用向此请求发送订阅数据
        webhook_port=9002,
    )
    
    try:
        # 启动客户端
        await client.start()
        print("✅ RPC客户端已启动")
        
        # 🤖 与AI聊天
        print("\n🤖 与AI元宝聊天...")
        chat_result = await client.get_notes_brief_from_xhs(
            storage_file="data/note-brief-rpc.json",
            max_items=10,
            cookie_ids=["28ba44f1-bb67-41ab-86f0-a3d049d902aa"]
        )
        print(f"AI回复: {chat_result.get('data', 'N/A')}")
        
        # # 📱 获取小红书笔记
        # print("\n📱 获取小红书美食笔记...")
        # notes = await client_sdk.get_notes_brief_from_xhs(
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
        # search_result = await client_sdk.search_notes_from_xhs(
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
    