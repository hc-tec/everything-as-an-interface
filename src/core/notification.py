from src.config import get_logger
import asyncio
import json
import time
import smtplib
import httpx
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union
from datetime import datetime

logger = get_logger(__name__)

class NotificationChannel:
    """通知渠道基类"""
    
    def __init__(self, channel_id: str, name: str, config: Dict[str, Any]) -> None:
        """
        初始化通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
        """
        self.channel_id = channel_id
        self.name = name
        self.config = config
        self.enabled = True
    
    async def send(self, title: str, message: str, level: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            
        Returns:
            发送结果
        """
        raise NotImplementedError("子类必须实现send方法")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "id": self.channel_id,
            "name": self.name,
            "type": self.__class__.__name__,
            "enabled": self.enabled,
            "config": {k: v for k, v in self.config.items() if k not in ["password", "token", "secret"]}
        }


class EmailChannel(NotificationChannel):
    """邮件通知渠道"""
    
    async def send(self, title: str, message: str, level: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送邮件通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            
        Returns:
            发送结果
        """
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg["Subject"] = f"[{level.upper()}] {title}"
            msg["From"] = self.config["sender"]
            msg["To"] = self.config["recipient"]
            
            # 邮件内容
            body = f"""
            <html>
            <body>
                <h2>{title}</h2>
                <p><strong>级别:</strong> {level}</p>
                <p><strong>时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>内容:</strong> {message}</p>
                <hr>
                <pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, "html", "utf-8"))
            
            # 发送邮件
            with smtplib.SMTP_SSL(self.config["smtp_server"], self.config["smtp_port"]) as server:
                server.login(self.config["username"], self.config["password"])
                server.send_message(msg)
            
            logger.info(f"邮件通知已发送: {title}")
            return {"success": True, "message": "邮件发送成功"}
        
        except Exception as e:
            logger.error(f"发送邮件通知失败: {str(e)}")
            return {"success": False, "message": str(e)}


class WebhookChannel(NotificationChannel):
    """Webhook通知渠道"""
    
    async def send(self, title: str, message: str, level: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送Webhook通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            
        Returns:
            发送结果
        """
        try:
            # 构建通知数据
            payload = {
                "title": title,
                "message": message,
                "level": level,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            # 添加自定义头信息
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "EverythingAsAnInterface/1.0"
            }
            
            if "headers" in self.config:
                headers.update(self.config["headers"])
                
            # 发送请求
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["url"],
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
                
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook通知已发送: {title}")
                return {"success": True, "status_code": response.status_code}
            else:
                logger.warning(f"Webhook通知发送失败: {response.status_code}, {response.text}")
                return {
                    "success": False, 
                    "status_code": response.status_code,
                    "message": response.text
                }
                
        except Exception as e:
            logger.error(f"发送Webhook通知失败: {str(e)}")
            return {"success": False, "message": str(e)}


class ConsoleChannel(NotificationChannel):
    """控制台通知渠道"""
    
    async def send(self, title: str, message: str, level: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送控制台通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            
        Returns:
            发送结果
        """
        # 格式化输出
        log_message = f"\n===== {level.upper()} NOTIFICATION =====\n"
        log_message += f"Title: {title}\n"
        log_message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_message += f"Message: {message}\n"
        log_message += f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}\n"
        log_message += "================================\n"
        
        # 根据级别选择日志级别
        if level == "debug":
            logger.debug(log_message)
        elif level == "info":
            logger.info(log_message)
        elif level == "warning":
            logger.warning(log_message)
        elif level == "error":
            logger.error(log_message)
        elif level == "critical":
            logger.critical(log_message)
        else:
            logger.info(log_message)
        
        return {"success": True, "message": "控制台通知已发送"}


class CustomChannel(NotificationChannel):
    """自定义通知渠道"""
    
    def __init__(self, channel_id: str, name: str, config: Dict[str, Any], 
                handler: Callable[[str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        初始化自定义通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
            handler: 自定义处理函数
        """
        super().__init__(channel_id, name, config)
        self.handler = handler
    
    async def send(self, title: str, message: str, level: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送自定义通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            
        Returns:
            发送结果
        """
        try:
            return await self.handler(title, message, level, data)
        except Exception as e:
            logger.error(f"发送自定义通知失败: {str(e)}")
            return {"success": False, "message": str(e)}


class Notification:
    """通知对象，表示一条通知记录"""
    
    def __init__(self, notification_id: str, title: str, message: str, level: str, 
                data: Dict[str, Any], channels: Optional[List[str]] = None) -> None:
        """
        初始化通知
        
        Args:
            notification_id: 通知ID
            title: 通知标题
            message: 通知内容
            level: 通知级别
            data: 通知数据
            channels: 通知渠道ID列表
        """
        self.notification_id = notification_id
        self.title = title
        self.message = message
        self.level = level
        self.data = data
        self.channels = channels or []
        self.created_at = datetime.now()
        self.sent_to = {}  # 记录发送结果：{channel_id: {success, message}}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "id": self.notification_id,
            "title": self.title,
            "message": self.message,
            "level": self.level,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "channels": self.channels,
            "sent_to": self.sent_to
        }


class NotificationCenter:
    """通知中心：负责管理和发送通知"""
    
    def __init__(self) -> None:
        """初始化通知中心"""
        self.channels: Dict[str, NotificationChannel] = {}
        self.notifications: List[Notification] = []
        self.level_thresholds = {
            "debug": 0,
            "info": 1,
            "warning": 2,
            "error": 3,
            "critical": 4
        }
        self.default_level = "info"
        self.default_channel = None
        self.max_history = 100
        
        # 注册默认渠道
        self.register_channel("console", "控制台通知", {}, ConsoleChannel)
    
    def register_channel(self, channel_id: str, name: str, config: Dict[str, Any], channel_class: type) -> str:
        """
        注册通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
            channel_class: 渠道类
            
        Returns:
            渠道ID
        """
        if channel_id in self.channels:
            logger.warning(f"通知渠道已存在: {channel_id}")
            return channel_id
            
        channel = channel_class(channel_id, name, config)
        self.channels[channel_id] = channel
        
        # 如果是首个渠道或者是控制台渠道，设为默认渠道
        if self.default_channel is None or channel_id == "console":
            self.default_channel = channel_id
            
        logger.info(f"注册通知渠道: {channel_id} ({name})")
        return channel_id
    
    def register_email_channel(self, channel_id: str, name: str, config: Dict[str, Any]) -> str:
        """
        注册邮件通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
            
        Returns:
            渠道ID
        """
        return self.register_channel(channel_id, name, config, EmailChannel)
    
    def register_webhook_channel(self, channel_id: str, name: str, config: Dict[str, Any]) -> str:
        """
        注册Webhook通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
            
        Returns:
            渠道ID
        """
        return self.register_channel(channel_id, name, config, WebhookChannel)
    
    def register_custom_channel(self, channel_id: str, name: str, config: Dict[str, Any], 
                              handler: Callable[[str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> str:
        """
        注册自定义通知渠道
        
        Args:
            channel_id: 渠道ID
            name: 渠道名称
            config: 渠道配置
            handler: 自定义处理函数
            
        Returns:
            渠道ID
        """
        channel = CustomChannel(channel_id, name, config, handler)
        self.channels[channel_id] = channel
        logger.info(f"注册自定义通知渠道: {channel_id} ({name})")
        return channel_id
    
    def remove_channel(self, channel_id: str) -> bool:
        """
        移除通知渠道
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            是否成功移除
        """
        if channel_id in self.channels:
            del self.channels[channel_id]
            
            # 如果移除的是默认渠道，则重新选择默认渠道
            if self.default_channel == channel_id:
                if "console" in self.channels:
                    self.default_channel = "console"
                elif self.channels:
                    self.default_channel = next(iter(self.channels))
                else:
                    self.default_channel = None
                    
            logger.info(f"移除通知渠道: {channel_id}")
            return True
        return False
    
    def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """
        获取通知渠道
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            通知渠道
        """
        return self.channels.get(channel_id)
    
    def get_all_channels(self) -> List[Dict[str, Any]]:
        """
        获取所有通知渠道
        
        Returns:
            通知渠道列表
        """
        return [channel.to_dict() for channel in self.channels.values()]
    
    def set_default_channel(self, channel_id: str) -> bool:
        """
        设置默认通知渠道
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            是否成功设置
        """
        if channel_id in self.channels:
            self.default_channel = channel_id
            logger.info(f"设置默认通知渠道: {channel_id}")
            return True
        return False
    
    def set_level_threshold(self, channel_id: str, level: str) -> bool:
        """
        设置渠道通知级别阈值
        
        Args:
            channel_id: 渠道ID
            level: 通知级别
            
        Returns:
            是否成功设置
        """
        if level not in self.level_thresholds:
            logger.error(f"无效的通知级别: {level}")
            return False
            
        if channel_id not in self.channels:
            logger.error(f"通知渠道不存在: {channel_id}")
            return False
            
        self.channels[channel_id].config["level_threshold"] = level
        logger.info(f"设置渠道 {channel_id} 的通知级别阈值: {level}")
        return True
    
    async def send_notification(self, title: str, message: str, level: Optional[str] = None, 
                             data: Optional[Dict[str, Any]] = None, channels: Optional[List[str]] = None) -> str:
        """
        发送通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别，默认为info
            data: 通知数据，默认为空字典
            channels: 通知渠道ID列表，默认为默认渠道
            
        Returns:
            通知ID
        """
        # 使用默认值
        level = level or self.default_level
        data = data or {}
        
        # 如果未指定渠道，使用默认渠道
        if not channels:
            if self.default_channel:
                channels = [self.default_channel]
            else:
                logger.warning("未指定通知渠道且无默认渠道")
                channels = []
        
        # 创建通知
        notification_id = str(uuid.uuid4())
        notification = Notification(
            notification_id=notification_id,
            title=title,
            message=message,
            level=level,
            data=data,
            channels=channels
        )
        
        # 记录通知
        self.notifications.append(notification)
        
        # 限制历史记录数量
        if len(self.notifications) > self.max_history:
            self.notifications = self.notifications[-self.max_history:]
        
        # 发送到各个渠道
        for channel_id in channels:
            channel = self.get_channel(channel_id)
            if not channel:
                logger.warning(f"通知渠道不存在: {channel_id}")
                notification.sent_to[channel_id] = {
                    "success": False,
                    "message": "通知渠道不存在"
                }
                continue
                
            # 检查是否启用
            if not channel.enabled:
                notification.sent_to[channel_id] = {
                    "success": False,
                    "message": "通知渠道已禁用"
                }
                continue
                
            # 检查级别阈值
            threshold_level = channel.config.get("level_threshold", "debug")
            if self.level_thresholds[level] < self.level_thresholds[threshold_level]:
                notification.sent_to[channel_id] = {
                    "success": False,
                    "message": f"通知级别 {level} 低于渠道阈值 {threshold_level}"
                }
                continue
            
            # 发送通知
            try:
                result = await channel.send(title, message, level, data)
                notification.sent_to[channel_id] = result
            except Exception as e:
                logger.error(f"通知发送失败: {str(e)}")
                notification.sent_to[channel_id] = {
                    "success": False,
                    "message": str(e)
                }
        
        return notification_id
    
    def get_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """
        获取通知
        
        Args:
            notification_id: 通知ID
            
        Returns:
            通知信息
        """
        for notification in self.notifications:
            if notification.notification_id == notification_id:
                return notification.to_dict()
        return None
    
    def get_all_notifications(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有通知
        
        Args:
            limit: 返回的最大数量
            
        Returns:
            通知列表
        """
        notifications = [n.to_dict() for n in sorted(
            self.notifications, 
            key=lambda x: x.created_at, 
            reverse=True
        )]
        
        if limit and limit > 0:
            return notifications[:limit]
        return notifications