# RPC客户端使用指南

## 概述

EAI RPC客户端提供了类似RPC的接口，让你可以像调用本地函数一样调用远程插件，而无需手动处理HTTP请求和webhook。

## 特性

- 🚀 **简单易用**: 像调用本地函数一样调用远程插件
- 🔄 **自动化处理**: 自动处理webhook注册、事件监听和结果返回
- ⚡ **异步支持**: 支持异步和同步两种调用方式
- 🛡️ **错误处理**: 内置超时、重试和错误处理机制
- 🔐 **安全验证**: 支持HMAC签名验证
- 📦 **批量处理**: 支持并发执行多个任务

## 快速开始

### 1. 安装依赖

```bash
pip install httpx fastapi uvicorn
```

### 2. 启动EAI服务器

```bash
# 在项目根目录下启动API服务器
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

### 3. 使用RPC客户端

```python
import asyncio
from client_sdk.rpc_client import EAIRPCClient


async def main():
   # 创建客户端
   client = EAIRPCClient(
      base_url="http://localhost:8000",
      api_key="your-api-key"
   )

   try:
      # 启动客户端
      await client.start()

      # 🤖 与AI聊天
      chat_result = await client.chat_with_yuanbao("你好！")
      print(f"AI回复: {chat_result}")

      # 📱 获取小红书笔记
      notes = await client.get_notes_brief_from_xhs(
         keywords=["美食", "推荐"],
         max_items=10
      )
      print(f"获取到 {len(notes.get('items', []))} 条笔记")

   finally:
      await client.stop()


if __name__ == "__main__":
   asyncio.run(main())
```

## API参考

### EAIRPCClient

#### 初始化参数

- `base_url` (str): EAI服务器地址，默认 `http://localhost:8000`
- `api_key` (str): API密钥
- `webhook_host` (str): Webhook服务器监听地址，默认 `0.0.0.0`
- `webhook_port` (int): Webhook服务器端口，默认 `9001`
- `webhook_secret` (str, 可选): Webhook签名密钥，自动生成

#### 生命周期方法

```python
# 启动客户端（必须调用）
await client.start()

# 停止客户端（建议在finally中调用）
await client.stop()
```

#### AI聊天方法

```python
# 与AI元宝聊天
result = await client.chat_with_yuanbao(
    message="你好，请介绍一下自己",
    headless=True  # 可选参数
)
```

#### 小红书相关方法

```python
# 获取笔记摘要
notes_brief = await client.get_notes_brief_from_xhs(
    keywords=["美食", "探店"],
    max_items=20,
    max_seconds=300,
    headless=True,
    cookie_ids=["xhs_user_1"]  # 可选，使用保存的cookie
)

# 获取笔记详情
notes_details = await client.get_notes_details_from_xhs(
    keywords=["旅行", "攻略"],
    max_items=10,
    max_seconds=180
)

# 搜索笔记
search_result = await client.search_notes_from_xhs(
    keywords=["咖啡", "拿铁"],
    max_items=15
)

# 获取收藏
favorites = await client.get_favorites_from_xhs(
    max_items=50,
    cookie_ids=["xhs_user_1"]
)
```

#### 通用插件调用

```python
# 调用任意插件
result = await client.call_plugin(
    plugin_id="custom_plugin",
    config={
        "param1": "value1",
        "param2": "value2"
    },
    timeout=300.0
)
```

### EAIRPCClientSync (同步版本)

如果你更喜欢同步调用，可以使用同步版本：

```python
from client_sdk.rpc_client import EAIRPCClientSync

# 创建同步客户端
client = EAIRPCClientSync(
   base_url="http://localhost:8000",
   api_key="your-api-key"
)

try:
   client.start()

   # 同步调用
   result = client.get_notes_brief_from_xhs(["美食"], max_items=5)
   print(f"获取到 {len(result.get('items', []))} 条笔记")

finally:
   client.stop()
```

## 高级用法

### 批量并发处理

```python
async def batch_processing():
    client = EAIRPCClient("http://localhost:8000", "your-api-key")
    
    try:
        await client.start()
        
        # 并发执行多个任务
        tasks = [
            client.get_notes_brief_from_xhs(["美食"], max_items=5),
            client.get_notes_brief_from_xhs(["旅行"], max_items=5),
            client.get_notes_brief_from_xhs(["摄影"], max_items=5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        for i, result in enumerate(results):
            print(f"任务 {i+1}: {len(result.get('items', []))} 条结果")
            
    finally:
        await client.stop()
```

### 使用上下文管理器

```python
class EAIHelper:
    def __init__(self, base_url: str, api_key: str):
        self.client = EAIRPCClientSync(base_url, api_key)
    
    def __enter__(self):
        self.client.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.stop()
    
    def search_content(self, keywords, max_items=10):
        return self.client.get_notes_brief_from_xhs(keywords, max_items=max_items)

# 使用
with EAIHelper("http://localhost:8000", "your-api-key") as helper:
    result = helper.search_content(["美食", "推荐"])
    print(f"找到 {len(result.get('items', []))} 条内容")
```

### 错误处理

```python
try:
    result = await client.get_notes_brief_from_xhs(["美食"], max_items=10)
except TimeoutError:
    print("请求超时")
except Exception as e:
    print(f"请求失败: {e}")
```

## 配置说明

### 通用配置参数

所有插件方法都支持以下通用参数：

- `headless` (bool): 是否无头模式运行浏览器，默认 `True`
- `cookie_ids` (List[str]): 使用的Cookie ID列表
- `viewport` (Dict): 浏览器视口大小，如 `{"width": 1920, "height": 1080}`
- `user_agent` (str): 自定义User-Agent
- `extra_http_headers` (Dict): 额外的HTTP头

### 小红书插件特定参数

- `max_items` (int): 最大采集条数，默认 `20`
- `max_seconds` (int): 最大执行时间（秒），默认 `300`
- `scroll_pause_ms` (int): 滚动暂停时间（毫秒），默认 `1000`
- `task_type` (str): 任务类型，如 `"briefs"`, `"details"`, `"favorites"`

## 故障排除

### 常见问题

1. **连接失败**
   - 确保EAI服务器正在运行
   - 检查`base_url`是否正确
   - 验证API密钥是否有效

2. **Webhook端口冲突**
   - 修改`webhook_port`参数使用不同端口
   - 确保端口未被其他程序占用

3. **请求超时**
   - 增加`timeout`参数值
   - 检查网络连接
   - 确认目标网站可访问

4. **Cookie失效**
   - 重新登录获取新的Cookie
   - 检查`cookie_ids`是否正确

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 性能优化

1. **复用客户端实例**: 避免频繁创建和销毁客户端
2. **合理设置超时**: 根据任务复杂度调整超时时间
3. **批量处理**: 使用`asyncio.gather()`并发执行多个任务
4. **资源清理**: 始终在`finally`块中调用`stop()`

## 示例文件

项目中提供了以下示例文件：

- `examples/quick_start_rpc.py`: 快速开始示例
- `examples/rpc_client_example.py`: 完整功能示例
- `examples/webhook_receiver.py`: Webhook接收器示例

## 与传统方式对比

### 传统方式（复杂）

```python
# 1. 创建topic
response = requests.post(f"{base_url}/api/v1/topics", json={...})
topic_id = response.json()["topic_id"]

# 2. 创建subscription
response = requests.post(f"{base_url}/api/v1/topics/{topic_id}/subscriptions", json={...})

# 3. 启动webhook服务器
app = FastAPI()
@app.post("/webhook")
async def webhook_handler(request: Request):
    # 处理webhook...

# 4. 执行插件（通过一次性任务）
response = requests.post(f"{base_url}/api/v1/tasks", json={
    "plugin_id": plugin_id,
    "run_mode": "once",
    "config": {...},
    "topic_id": topic_id
})

# 5. 等待webhook响应...
```

### RPC方式（简单）

```python
# 一行代码搞定！
result = await client.get_notes_brief_from_xhs(["美食"], max_items=10)
```

## 总结

EAI RPC客户端大大简化了插件调用的复杂性，让你可以专注于业务逻辑而不是底层的HTTP和Webhook处理。通过提供类似RPC的接口，它让远程插件调用变得像调用本地函数一样简单。