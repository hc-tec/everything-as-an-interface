import logging
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Set, Optional, Callable, Awaitable
from datetime import datetime
import hashlib

logger = logging.getLogger("subscription")

class Subscriber:
    """订阅者类，表示一个数据订阅者"""
    
    def __init__(self, 
                subscriber_id: str, 
                callback: Callable[[Dict[str, Any]], Awaitable[None]],
                filters: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化订阅者
        
        Args:
            subscriber_id: 订阅者ID
            callback: 数据回调函数
            filters: 数据过滤条件
        """
        self.subscriber_id = subscriber_id
        self.callback = callback
        self.filters = filters or {}
        self.created_at = datetime.now()
        self.last_delivery: Optional[datetime] = None
        self.delivery_count = 0
        self.error_count = 0
    
    def matches(self, data: Dict[str, Any]) -> bool:
        """
        检查数据是否匹配过滤条件
        
        Args:
            data: 数据
            
        Returns:
            是否匹配
        """
        if not self.filters:
            return True
            
        for key, value in self.filters.items():
            # 支持点号访问嵌套属性
            if "." in key:
                parts = key.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False
                if current != value:
                    return False
            # 简单键值匹配
            elif key not in data or data[key] != value:
                return False
                
        return True
    
    async def deliver(self, data: Dict[str, Any]) -> bool:
        """
        向订阅者推送数据
        
        Args:
            data: 数据
            
        Returns:
            是否成功推送
        """
        try:
            await self.callback(data)
            self.last_delivery = datetime.now()
            self.delivery_count += 1
            return True
        except Exception as e:
            logger.error(f"向订阅者 {self.subscriber_id} 推送数据失败: {str(e)}")
            self.error_count += 1
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "subscriber_id": self.subscriber_id,
            "filters": self.filters,
            "created_at": self.created_at.isoformat(),
            "last_delivery": self.last_delivery.isoformat() if self.last_delivery else None,
            "delivery_count": self.delivery_count,
            "error_count": self.error_count
        }


class Topic:
    """主题类，表示一个数据主题"""
    
    def __init__(self, topic_id: str, name: str, description: str = "") -> None:
        """
        初始化主题
        
        Args:
            topic_id: 主题ID
            name: 主题名称
            description: 主题描述
        """
        self.topic_id = topic_id
        self.name = name
        self.description = description
        self.subscribers: Dict[str, Subscriber] = {}
        self.last_data: Optional[Dict[str, Any]] = None
        self.last_update: Optional[datetime] = None
        self.data_hash: Optional[str] = None
        self.update_count = 0
    
    def add_subscriber(self, subscriber: Subscriber) -> None:
        """
        添加订阅者
        
        Args:
            subscriber: 订阅者对象
        """
        self.subscribers[subscriber.subscriber_id] = subscriber
        logger.info(f"主题 {self.topic_id} 添加订阅者: {subscriber.subscriber_id}")
    
    def remove_subscriber(self, subscriber_id: str) -> bool:
        """
        移除订阅者
        
        Args:
            subscriber_id: 订阅者ID
            
        Returns:
            是否成功移除
        """
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            logger.info(f"主题 {self.topic_id} 移除订阅者: {subscriber_id}")
            return True
        return False
    
    def get_subscriber(self, subscriber_id: str) -> Optional[Subscriber]:
        """
        获取订阅者
        
        Args:
            subscriber_id: 订阅者ID
            
        Returns:
            订阅者对象
        """
        return self.subscribers.get(subscriber_id)
    
    def get_subscribers(self) -> List[Dict[str, Any]]:
        """
        获取所有订阅者
        
        Returns:
            订阅者列表
        """
        return [subscriber.to_dict() for subscriber in self.subscribers.values()]
    
    async def publish(self, data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        发布数据到主题
        
        Args:
            data: 数据
            force: 是否强制推送，即使数据未变更
            
        Returns:
            发布结果，包含成功和失败的订阅者数量
        """
        # 计算数据哈希，用于检测变更
        new_hash = self._hash_data(data)
        
        # 如果数据未变更且不强制推送，则跳过
        if not force and self.data_hash and self.data_hash == new_hash:
            return {
                "topic_id": self.topic_id,
                "unchanged": True,
                "subscribers": 0,
                "success": 0,
                "failed": 0
            }
        
        # 更新主题状态
        self.last_data = data
        self.last_update = datetime.now()
        self.data_hash = new_hash
        self.update_count += 1
        
        # 推送给所有匹配的订阅者
        success_count = 0
        failed_count = 0
        
        for subscriber in self.subscribers.values():
            if subscriber.matches(data):
                success = await subscriber.deliver(data)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
        
        logger.info(f"主题 {self.topic_id} 发布数据: 成功 {success_count}, 失败 {failed_count}")
        
        return {
            "topic_id": self.topic_id,
            "unchanged": False,
            "subscribers": len(self.subscribers),
            "success": success_count,
            "failed": failed_count
        }
    
    def _hash_data(self, data: Dict[str, Any]) -> str:
        """
        计算数据哈希值
        
        Args:
            data: 数据
            
        Returns:
            数据哈希值
        """
        # 将数据序列化为JSON字符串，然后计算SHA256哈希
        try:
            serialized = json.dumps(data, sort_keys=True)
            return hashlib.sha256(serialized.encode()).hexdigest()
        except Exception as e:
            logger.error(f"计算数据哈希失败: {str(e)}")
            # 如果序列化失败，则使用时间戳作为哈希
            return f"timestamp_{time.time()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "description": self.description,
            "subscriber_count": len(self.subscribers),
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "update_count": self.update_count
        }


class SubscriptionSystem:
    """订阅系统：负责管理主题和订阅关系"""
    
    def __init__(self) -> None:
        """初始化订阅系统"""
        self.topics: Dict[str, Topic] = {}
    
    def create_topic(self, name: str, description: str = "", topic_id: Optional[str] = None) -> str:
        """
        创建主题
        
        Args:
            name: 主题名称
            description: 主题描述
            topic_id: 可选的主题ID，若不提供则自动生成
            
        Returns:
            主题ID
        """
        # 生成主题ID
        topic_id = topic_id or str(uuid.uuid4())
        
        # 创建主题
        topic = Topic(topic_id=topic_id, name=name, description=description)
        
        # 添加到主题列表
        self.topics[topic_id] = topic
        logger.info(f"创建主题: {topic_id} ({name})")
        
        return topic_id
    
    def remove_topic(self, topic_id: str) -> bool:
        """
        移除主题
        
        Args:
            topic_id: 主题ID
            
        Returns:
            是否成功移除
        """
        if topic_id in self.topics:
            del self.topics[topic_id]
            logger.info(f"移除主题: {topic_id}")
            return True
        return False
    
    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """
        获取主题
        
        Args:
            topic_id: 主题ID
            
        Returns:
            主题对象
        """
        return self.topics.get(topic_id)
    
    def get_all_topics(self) -> List[Dict[str, Any]]:
        """
        获取所有主题
        
        Returns:
            主题列表
        """
        return [topic.to_dict() for topic in self.topics.values()]
    
    def subscribe(self, 
                 topic_id: str, 
                 callback: Callable[[Dict[str, Any]], Awaitable[None]],
                 filters: Optional[Dict[str, Any]] = None,
                 subscriber_id: Optional[str] = None) -> Optional[str]:
        """
        订阅主题
        
        Args:
            topic_id: 主题ID
            callback: 数据回调函数
            filters: 数据过滤条件
            subscriber_id: 可选的订阅者ID，若不提供则自动生成
            
        Returns:
            订阅者ID，若主题不存在则返回None
        """
        topic = self.get_topic(topic_id)
        if not topic:
            logger.error(f"订阅失败: 主题 {topic_id} 不存在")
            return None
        
        # 生成订阅者ID
        subscriber_id = subscriber_id or str(uuid.uuid4())
        
        # 创建订阅者
        subscriber = Subscriber(
            subscriber_id=subscriber_id,
            callback=callback,
            filters=filters
        )
        
        # 添加到主题
        topic.add_subscriber(subscriber)
        
        return subscriber_id
    
    def unsubscribe(self, topic_id: str, subscriber_id: str) -> bool:
        """
        取消订阅
        
        Args:
            topic_id: 主题ID
            subscriber_id: 订阅者ID
            
        Returns:
            是否成功取消
        """
        topic = self.get_topic(topic_id)
        if not topic:
            logger.error(f"取消订阅失败: 主题 {topic_id} 不存在")
            return False
            
        return topic.remove_subscriber(subscriber_id)
    
    async def publish(self, topic_id: str, data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        发布数据到主题
        
        Args:
            topic_id: 主题ID
            data: 数据
            force: 是否强制推送，即使数据未变更
            
        Returns:
            发布结果，包含成功和失败的订阅者数量
        """
        topic = self.get_topic(topic_id)
        if not topic:
            logger.error(f"发布失败: 主题 {topic_id} 不存在")
            return {
                "topic_id": topic_id,
                "error": "主题不存在",
                "success": 0,
                "failed": 0
            }
            
        return await topic.publish(data, force)
    
    def get_last_data(self, topic_id: str) -> Optional[Dict[str, Any]]:
        """
        获取主题的最新数据
        
        Args:
            topic_id: 主题ID
            
        Returns:
            最新数据，若主题不存在则返回None
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return None
            
        return topic.last_data