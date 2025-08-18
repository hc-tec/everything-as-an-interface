# Everything-as-an-Interface API 文档

## 概述

Everything-as-an-Interface 提供了一套完整的 API 接口，用于管理插件、任务、账户和数据采集。本文档详细描述了所有可用的 API 接口。

## 基础信息

- **基础 URL**: `http://localhost:8000/api/v1`
- **认证方式**: Bearer Token
- **数据格式**: JSON
- **字符编码**: UTF-8

## 通用响应格式

### 成功响应

```json
{
    "success": true,
    "data": {},
    "message": "操作成功",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### 错误响应

```json
{
    "success": false,
    "error": {
        "code": "ERROR_CODE",
        "message": "错误描述",
        "details": {}
    },
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## 认证接口

### 获取访问令牌

**POST** `/auth/token`

获取 API 访问令牌。

**请求体**:
```json
{
    "username": "admin",
    "password": "password"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 3600
    }
}
```

### 刷新令牌

**POST** `/auth/refresh`

刷新访问令牌。

**请求头**:
```
Authorization: Bearer <access_token>
```

**响应**:
```json
{
    "success": true,
    "data": {
        "access_token": "new_token_here",
        "expires_in": 3600
    }
}
```

## 插件管理接口

### 获取所有插件

**GET** `/plugins`

获取系统中所有可用的插件列表。

**响应**:
```json
{
    "success": true,
    "data": {
        "plugins": [
            {
                "id": "xiaohongshu",
                "name": "小红书",
                "description": "小红书数据采集插件",
                "version": "2.0.0",
                "author": "开发团队",
                "status": "available",
                "loaded": false
            }
        ],
        "total": 1
    }
}
```

### 获取插件详情

**GET** `/plugins/{plugin_id}`

获取指定插件的详细信息。

**路径参数**:
- `plugin_id` (string): 插件ID

**响应**:
```json
{
    "success": true,
    "data": {
        "id": "xiaohongshu",
        "name": "小红书",
        "description": "小红书数据采集插件",
        "version": "2.0.0",
        "author": "开发团队",
        "config_schema": {
            "type": "object",
            "properties": {
                "search_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "搜索关键词列表"
                },
                "max_pages": {
                    "type": "integer",
                    "default": 5,
                    "description": "最大采集页数"
                }
            },
            "required": ["search_keywords"]
        },
        "status": "available",
        "loaded": false
    }
}
```

### 加载插件

**POST** `/plugins/{plugin_id}/load`

加载指定的插件。

**路径参数**:
- `plugin_id` (string): 插件ID

**请求体**:
```json
{
    "config": {
        "headless": true,
        "cookie_ids": ["xhs_user_1"]
    }
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "plugin_id": "xiaohongshu",
        "status": "loaded",
        "instance_id": "xiaohongshu_001"
    }
}
```

### 卸载插件

**POST** `/plugins/{plugin_id}/unload`

卸载指定的插件。

**响应**:
```json
{
    "success": true,
    "data": {
        "plugin_id": "xiaohongshu",
        "status": "unloaded"
    }
}
```

## 任务管理接口

### 获取所有任务

**GET** `/tasks`

获取系统中所有任务的列表。

**查询参数**:
- `status` (string, 可选): 任务状态过滤 (`pending`, `running`, `completed`, `failed`)
- `plugin_id` (string, 可选): 插件ID过滤
- `page` (integer, 可选): 页码，默认为1
- `limit` (integer, 可选): 每页数量，默认为20

**响应**:
```json
{
    "success": true,
    "data": {
        "tasks": [
            {
                "id": "task_001",
                "plugin_id": "xiaohongshu",
                "status": "running",
                "config": {
                    "search_keywords": ["美食", "旅行"],
                    "max_pages": 5
                },
                "interval": 300,
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
                "next_run": "2024-01-01T12:05:00Z",
                "last_result": {
                    "success": true,
                    "items_collected": 25,
                    "execution_time": 45.2
                }
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 1,
            "pages": 1
        }
    }
}
```

### 创建任务

**POST** `/tasks`

创建新的数据采集任务。

**请求体**:
```json
{
    "plugin_id": "xiaohongshu",
    "config": {
        "search_keywords": ["美食", "旅行"],
        "max_pages": 5,
        "headless": true,
        "cookie_ids": ["xhs_user_1"]
    },
    "interval": 300,
    "callback_url": "https://your-api.com/webhook/data",
    "enabled": true
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "task_id": "task_002",
        "status": "created",
        "next_run": "2024-01-01T12:10:00Z"
    }
}
```

### 获取任务详情

**GET** `/tasks/{task_id}`

获取指定任务的详细信息。

**路径参数**:
- `task_id` (string): 任务ID

**响应**:
```json
{
    "success": true,
    "data": {
        "id": "task_001",
        "plugin_id": "xiaohongshu",
        "status": "running",
        "config": {
            "search_keywords": ["美食", "旅行"],
            "max_pages": 5
        },
        "interval": 300,
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "next_run": "2024-01-01T12:05:00Z",
        "execution_history": [
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "status": "success",
                "items_collected": 25,
                "execution_time": 45.2,
                "error": null
            }
        ]
    }
}
```

### 更新任务

**PUT** `/tasks/{task_id}`

更新指定任务的配置。

**请求体**:
```json
{
    "config": {
        "search_keywords": ["美食", "旅行", "摄影"],
        "max_pages": 10
    },
    "interval": 600,
    "enabled": true
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "task_id": "task_001",
        "status": "updated",
        "next_run": "2024-01-01T12:15:00Z"
    }
}
```

### 删除任务

**DELETE** `/tasks/{task_id}`

删除指定的任务。

**响应**:
```json
{
    "success": true,
    "data": {
        "task_id": "task_001",
        "status": "deleted"
    }
}
```

### 手动执行任务

**POST** `/tasks/{task_id}/execute`

立即执行指定的任务。

**响应**:
```json
{
    "success": true,
    "data": {
        "task_id": "task_001",
        "execution_id": "exec_001",
        "status": "started"
    }
}
```

### 暂停/恢复任务

**POST** `/tasks/{task_id}/pause`

暂停指定的任务。

**POST** `/tasks/{task_id}/resume`

恢复指定的任务。

**响应**:
```json
{
    "success": true,
    "data": {
        "task_id": "task_001",
        "status": "paused"  // 或 "running"
    }
}
```

## 账户管理接口

### 获取所有平台

**GET** `/accounts/platforms`

获取支持的所有平台列表。

**响应**:
```json
{
    "success": true,
    "data": {
        "platforms": [
            {
                "id": "xiaohongshu",
                "name": "小红书",
                "icon": "xiaohongshu.png",
                "login_url": "https://www.xiaohongshu.com/login",
                "cookie_domains": [".xiaohongshu.com"],
                "requires_login": true
            }
        ]
    }
}
```

### 获取账户列表

**GET** `/accounts`

获取所有已保存的账户信息。

**查询参数**:
- `platform_id` (string, 可选): 平台ID过滤

**响应**:
```json
{
    "success": true,
    "data": {
        "accounts": [
            {
                "cookie_id": "xhs_user_1",
                "platform_id": "xiaohongshu",
                "name": "测试账户1",
                "created_at": "2024-01-01T10:00:00Z",
                "last_used": "2024-01-01T12:00:00Z",
                "status": "valid",
                "metadata": {
                    "username": "test_user",
                    "user_id": "123456"
                }
            }
        ]
    }
}
```

### 添加账户

**POST** `/accounts`

添加新的账户 Cookie。

**请求体**:
```json
{
    "platform_id": "xiaohongshu",
    "name": "测试账户2",
    "cookies": [
        {
            "name": "session",
            "value": "abc123def456",
            "domain": ".xiaohongshu.com",
            "path": "/",
            "expires": 1735689600
        }
    ],
    "metadata": {
        "username": "test_user2",
        "notes": "备用账户"
    }
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "cookie_id": "xhs_user_2",
        "status": "added"
    }
}
```

### 更新账户

**PUT** `/accounts/{cookie_id}`

更新指定账户的信息。

**请求体**:
```json
{
    "name": "更新后的账户名",
    "cookies": [
        {
            "name": "session",
            "value": "new_session_value",
            "domain": ".xiaohongshu.com",
            "path": "/",
            "expires": 1735689600
        }
    ]
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "cookie_id": "xhs_user_1",
        "status": "updated"
    }
}
```

### 删除账户

**DELETE** `/accounts/{cookie_id}`

删除指定的账户。

**响应**:
```json
{
    "success": true,
    "data": {
        "cookie_id": "xhs_user_1",
        "status": "deleted"
    }
}
```

### 验证账户

**POST** `/accounts/{cookie_id}/validate`

验证指定账户的有效性。

**响应**:
```json
{
    "success": true,
    "data": {
        "cookie_id": "xhs_user_1",
        "valid": true,
        "message": "账户有效",
        "checked_at": "2024-01-01T12:00:00Z"
    }
}
```

## 数据接口

### 获取采集数据

**GET** `/data`

获取采集到的数据。

**查询参数**:
- `task_id` (string, 可选): 任务ID过滤
- `plugin_id` (string, 可选): 插件ID过滤
- `start_date` (string, 可选): 开始日期 (ISO 8601)
- `end_date` (string, 可选): 结束日期 (ISO 8601)
- `page` (integer, 可选): 页码，默认为1
- `limit` (integer, 可选): 每页数量，默认为20

**响应**:
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": "data_001",
                "task_id": "task_001",
                "plugin_id": "xiaohongshu",
                "collected_at": "2024-01-01T12:00:00Z",
                "data": {
                    "title": "美食分享",
                    "content": "今天分享一道美味的菜...",
                    "author": "美食达人",
                    "likes": 1250,
                    "comments": 89,
                    "url": "https://www.xiaohongshu.com/explore/123456"
                }
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 150,
            "pages": 8
        }
    }
}
```

### 导出数据

**POST** `/data/export`

导出采集数据。

**请求体**:
```json
{
    "format": "csv",  // csv, json, xlsx
    "filters": {
        "task_id": "task_001",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-02T00:00:00Z"
    },
    "fields": ["title", "content", "author", "likes", "collected_at"]
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "export_id": "export_001",
        "status": "processing",
        "download_url": null,
        "estimated_completion": "2024-01-01T12:05:00Z"
    }
}
```

### 获取导出状态

**GET** `/data/export/{export_id}`

获取数据导出的状态。

**响应**:
```json
{
    "success": true,
    "data": {
        "export_id": "export_001",
        "status": "completed",
        "download_url": "/api/v1/data/download/export_001",
        "file_size": 2048576,
        "records_count": 1500,
        "created_at": "2024-01-01T12:00:00Z",
        "completed_at": "2024-01-01T12:03:00Z"
    }
}
```

## 通知接口

### 获取通知渠道

**GET** `/notifications/channels`

获取所有配置的通知渠道。

**响应**:
```json
{
    "success": true,
    "data": {
        "channels": [
            {
                "id": "email_001",
                "name": "邮件通知",
                "type": "EmailChannel",
                "enabled": true,
                "config": {
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "sender": "noreply@example.com",
                    "recipient": "admin@example.com"
                }
            }
        ]
    }
}
```

### 添加通知渠道

**POST** `/notifications/channels`

添加新的通知渠道。

**请求体**:
```json
{
    "name": "Webhook通知",
    "type": "webhook",
    "config": {
        "url": "https://your-webhook.com/notify",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer your_token"
        }
    },
    "level_threshold": "warning"
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "channel_id": "webhook_001",
        "status": "created"
    }
}
```

### 发送通知

**POST** `/notifications/send`

发送自定义通知。

**请求体**:
```json
{
    "title": "系统警告",
    "message": "检测到异常活动",
    "level": "warning",
    "data": {
        "task_id": "task_001",
        "error_count": 5
    },
    "channels": ["email_001", "webhook_001"]
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "notification_id": "notif_001",
        "status": "sent",
        "delivery_results": {
            "email_001": {"success": true},
            "webhook_001": {"success": true}
        }
    }
}
```

## 订阅接口

### 获取主题列表

**GET** `/subscriptions/topics`

获取所有可订阅的主题。

**响应**:
```json
{
    "success": true,
    "data": {
        "topics": [
            {
                "id": "task_results",
                "name": "任务结果",
                "description": "任务执行结果推送",
                "subscriber_count": 3,
                "last_published": "2024-01-01T12:00:00Z"
            }
        ]
    }
}
```

### 创建订阅

**POST** `/subscriptions`

创建新的数据订阅。

**请求体**:
```json
{
    "topic_id": "task_results",
    "callback_url": "https://your-api.com/webhook/results",
    "filters": {
        "plugin_id": "xiaohongshu",
        "status": "success"
    },
    "headers": {
        "Authorization": "Bearer your_token"
    }
}
```

**响应**:
```json
{
    "success": true,
    "data": {
        "subscription_id": "sub_001",
        "status": "active"
    }
}
```

### 取消订阅

**DELETE** `/subscriptions/{subscription_id}`

取消指定的订阅。

**响应**:
```json
{
    "success": true,
    "data": {
        "subscription_id": "sub_001",
        "status": "cancelled"
    }
}
```

## 系统接口

### 系统状态

**GET** `/system/status`

获取系统运行状态。

**响应**:
```json
{
    "success": true,
    "data": {
        "status": "healthy",
        "uptime": 86400,
        "version": "1.0.0",
        "components": {
            "scheduler": {"status": "running", "tasks_count": 5},
            "plugin_manager": {"status": "ready", "plugins_loaded": 3},
            "account_manager": {"status": "ready", "accounts_count": 10},
            "database": {"status": "connected", "response_time": 15},
            "redis": {"status": "connected", "memory_usage": "45%"}
        },
        "metrics": {
            "total_tasks": 25,
            "successful_executions": 230,
            "failed_executions": 5,
            "data_items_collected": 15420
        }
    }
}
```

### 系统配置

**GET** `/system/config`

获取系统配置信息。

**响应**:
```json
{
    "success": true,
    "data": {
        "environment": "production",
        "log_level": "INFO",
        "max_concurrent_tasks": 10,
        "default_task_timeout": 300,
        "browser_settings": {
            "default_headless": true,
            "default_viewport": {"width": 1280, "height": 800}
        }
    }
}
```

### 系统日志

**GET** `/system/logs`

获取系统日志。

**查询参数**:
- `level` (string, 可选): 日志级别过滤 (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `start_date` (string, 可选): 开始日期
- `end_date` (string, 可选): 结束日期
- `limit` (integer, 可选): 返回条数，默认为100

**响应**:
```json
{
    "success": true,
    "data": {
        "logs": [
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "level": "INFO",
                "logger": "scheduler",
                "message": "任务 task_001 执行成功",
                "extra": {
                    "task_id": "task_001",
                    "execution_time": 45.2
                }
            }
        ]
    }
}
```

## WebSocket 接口

### 实时事件流

**WebSocket** `/ws/events`

建立 WebSocket 连接以接收实时事件。

**连接参数**:
- `token`: 认证令牌
- `topics`: 订阅的主题列表（逗号分隔）

**示例连接**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events?token=your_token&topics=task_events,system_events');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('收到事件:', data);
};
```

**事件格式**:
```json
{
    "type": "task_completed",
    "topic": "task_events",
    "data": {
        "task_id": "task_001",
        "status": "success",
        "items_collected": 25,
        "execution_time": 45.2
    },
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## 错误代码

| 错误代码 | HTTP状态码 | 描述 |
|---------|-----------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `UNAUTHORIZED` | 401 | 未授权访问 |
| `FORBIDDEN` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT` | 409 | 资源冲突 |
| `VALIDATION_ERROR` | 422 | 数据验证失败 |
| `RATE_LIMITED` | 429 | 请求频率超限 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

## 限制说明

### 请求频率限制

- **认证接口**: 每分钟最多 10 次请求
- **数据查询接口**: 每分钟最多 100 次请求
- **管理接口**: 每分钟最多 60 次请求
- **WebSocket连接**: 每个用户最多 5 个并发连接

### 数据限制

- **单次查询**: 最多返回 1000 条记录
- **导出数据**: 单次最多导出 100,000 条记录
- **文件上传**: 最大 10MB
- **请求体大小**: 最大 1MB

## SDK 和示例

### Python SDK 示例

```python
import requests
from typing import Dict, Any, List

class EverythingAsInterfaceClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def get_plugins(self) -> List[Dict[str, Any]]:
        """获取所有插件"""
        response = requests.get(
            f'{self.base_url}/api/v1/plugins',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['data']['plugins']
    
    def create_task(self, plugin_id: str, config: Dict[str, Any], 
                   interval: int = 300) -> str:
        """创建任务"""
        data = {
            'plugin_id': plugin_id,
            'config': config,
            'interval': interval
        }
        response = requests.post(
            f'{self.base_url}/api/v1/tasks',
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['data']['task_id']
    
    def get_data(self, task_id: str = None, page: int = 1, 
                limit: int = 20) -> Dict[str, Any]:
        """获取采集数据"""
        params = {'page': page, 'limit': limit}
        if task_id:
            params['task_id'] = task_id
        
        response = requests.get(
            f'{self.base_url}/api/v1/data',
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['data']

# 使用示例
client = EverythingAsInterfaceClient(
    base_url='http://localhost:8000',
    token='your_access_token'
)

# 获取插件列表
plugins = client.get_plugins()
print(f'可用插件: {len(plugins)} 个')

# 创建任务
task_id = client.create_task(
    plugin_id='xiaohongshu',
    config={
        'search_keywords': ['美食'],
        'max_pages': 5,
        'headless': True
    },
    interval=300
)
print(f'任务已创建: {task_id}')

# 获取数据
data = client.get_data(task_id=task_id)
print(f'采集到 {len(data["items"])} 条数据')
```

### JavaScript SDK 示例

```javascript
class EverythingAsInterfaceClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async request(method, endpoint, data = null) {
        const url = `${this.baseUrl}/api/v1${endpoint}`;
        const options = {
            method,
            headers: this.headers
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    async getPlugins() {
        const result = await this.request('GET', '/plugins');
        return result.data.plugins;
    }

    async createTask(pluginId, config, interval = 300) {
        const data = {
            plugin_id: pluginId,
            config: config,
            interval: interval
        };
        const result = await this.request('POST', '/tasks', data);
        return result.data.task_id;
    }

    async getData(taskId = null, page = 1, limit = 20) {
        let endpoint = `/data?page=${page}&limit=${limit}`;
        if (taskId) {
            endpoint += `&task_id=${taskId}`;
        }
        const result = await this.request('GET', endpoint);
        return result.data;
    }

    // WebSocket 连接
    connectWebSocket(topics = []) {
        const token = this.headers.Authorization.split(' ')[1];
        const wsUrl = `ws://localhost:8000/ws/events?token=${token}&topics=${topics.join(',')}`;
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket 连接已建立');
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('收到事件:', data);
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
        };
        
        return ws;
    }
}

// 使用示例
const client = new EverythingAsInterfaceClient(
    'http://localhost:8000',
    'your_access_token'
);

// 获取插件列表
client.getPlugins().then(plugins => {
    console.log(`可用插件: ${plugins.length} 个`);
});

// 创建任务
client.createTask('xiaohongshu', {
    search_keywords: ['美食'],
    max_pages: 5,
    headless: true
}).then(taskId => {
    console.log(`任务已创建: ${taskId}`);
});

// 建立 WebSocket 连接
const ws = client.connectWebSocket(['task_events', 'system_events']);
```

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 支持插件管理、任务调度、账户管理
- 提供完整的 REST API
- 支持 WebSocket 实时事件推送

---

本文档将随着系统功能的更新而持续维护。如有疑问或建议，请通过项目的 Issue 系统反馈。