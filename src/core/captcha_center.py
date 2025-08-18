import logging
import asyncio
import base64
import io
import os
import json
from typing import Dict, Any, Optional, List, Callable, Awaitable
from abc import ABC, abstractmethod
from datetime import datetime
from PIL import Image

logger = logging.getLogger("captcha_center")

class CaptchaHandler(ABC):
    """验证码处理器抽象基类"""
    
    @abstractmethod
    async def solve(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解决验证码
        
        Args:
            captcha_data: 验证码数据
            
        Returns:
            处理结果，包含是否成功解决
        """
        pass

class ImageCaptchaHandler(CaptchaHandler):
    """图形验证码处理器"""
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解决图形验证码
        
        Args:
            captcha_data: 验证码数据，应包含图片内容
            
        Returns:
            处理结果，包含是否成功解决
        """
        # 示例实现：转发给人工处理
        return {
            "success": False,
            "message": "需要人工处理",
            "human_intervention_needed": True
        }

class SlideCaptchaHandler(CaptchaHandler):
    """滑动验证码处理器"""
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解决滑动验证码
        
        Args:
            captcha_data: 验证码数据，应包含背景图和滑块图片
            
        Returns:
            处理结果，包含是否成功解决，以及滑动偏移量
        """
        # 示例实现：转发给人工处理
        return {
            "success": False,
            "message": "需要人工处理",
            "human_intervention_needed": True
        }

class CustomCaptchaHandler(CaptchaHandler):
    """自定义验证码处理器"""
    
    def __init__(self, handler_func: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        初始化自定义验证码处理器
        
        Args:
            handler_func: 自定义处理函数
        """
        self.handler_func = handler_func
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用自定义函数解决验证码
        
        Args:
            captcha_data: 验证码数据
            
        Returns:
            处理结果
        """
        return await self.handler_func(captcha_data)

class HumanInterventionHandler(CaptchaHandler):
    """人工干预处理器"""
    
    def __init__(self, intervention_callback: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None) -> None:
        """
        初始化人工干预处理器
        
        Args:
            intervention_callback: 人工干预回调函数
        """
        self.intervention_callback = intervention_callback
        self.pending_captchas: Dict[str, Dict[str, Any]] = {}
    
    async def solve(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        请求人工解决验证码
        
        Args:
            captcha_data: 验证码数据
            
        Returns:
            处理结果
        """
        # 生成唯一ID
        captcha_id = captcha_data.get("id") or f"captcha_{datetime.now().timestamp()}"
        
        # 存储验证码数据
        self.pending_captchas[captcha_id] = {
            "data": captcha_data,
            "status": "pending",
            "created_at": datetime.now(),
            "result": None
        }
        
        # 如果提供了回调，则调用回调函数请求人工干预
        if self.intervention_callback:
            try:
                result = await self.intervention_callback(captcha_data)
                if result.get("success"):
                    self.pending_captchas[captcha_id]["status"] = "solved"
                    self.pending_captchas[captcha_id]["result"] = result
                    return result
            except Exception as e:
                logger.error(f"人工干预回调失败: {str(e)}")
        
        # 等待人工干预结果 (最多等待60秒)
        for _ in range(60):
            await asyncio.sleep(1)
            if (self.pending_captchas[captcha_id]["status"] == "solved" and 
                self.pending_captchas[captcha_id]["result"]):
                return self.pending_captchas[captcha_id]["result"]
        
        # 超时
        return {
            "success": False,
            "message": "人工干预超时",
            "captcha_id": captcha_id
        }
    
    def submit_result(self, captcha_id: str, result: Dict[str, Any]) -> bool:
        """
        提交人工干预结果
        
        Args:
            captcha_id: 验证码ID
            result: 处理结果
            
        Returns:
            是否成功提交
        """
        if captcha_id in self.pending_captchas:
            self.pending_captchas[captcha_id]["status"] = "solved"
            self.pending_captchas[captcha_id]["result"] = result
            return True
        return False
    
    def get_pending_captchas(self) -> List[Dict[str, Any]]:
        """
        获取待处理的验证码列表
        
        Returns:
            待处理验证码列表
        """
        result = []
        for captcha_id, captcha in self.pending_captchas.items():
            if captcha["status"] == "pending":
                result.append({
                    "id": captcha_id,
                    "data": captcha["data"],
                    "created_at": captcha["created_at"].isoformat()
                })
        return result

class CaptchaCenter:
    """验证码处理中心：负责处理各类验证码"""
    
    def __init__(self) -> None:
        """初始化验证码处理中心"""
        self.handlers: Dict[str, CaptchaHandler] = {}
        self.human_intervention = HumanInterventionHandler()
        
        # 注册默认处理器
        self.register_handler("image", ImageCaptchaHandler())
        self.register_handler("slide", SlideCaptchaHandler())
        self.register_handler("human", self.human_intervention)
    
    def register_handler(self, captcha_type: str, handler: CaptchaHandler) -> None:
        """
        注册验证码处理器
        
        Args:
            captcha_type: 验证码类型
            handler: 处理器实例
        """
        self.handlers[captcha_type] = handler
        logger.info(f"注册验证码处理器: {captcha_type}")
    
    def register_custom_handler(self, captcha_type: str, 
                               handler_func: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        注册自定义验证码处理器
        
        Args:
            captcha_type: 验证码类型
            handler_func: 处理函数
        """
        self.register_handler(captcha_type, CustomCaptchaHandler(handler_func))
    
    def set_human_intervention_callback(self, 
                                       callback: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        设置人工干预回调函数
        
        Args:
            callback: 回调函数
        """
        self.human_intervention = HumanInterventionHandler(callback)
        self.register_handler("human", self.human_intervention)
    
    async def solve_captcha(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解决验证码
        
        Args:
            captcha_data: 验证码数据，必须包含验证码类型
            
        Returns:
            处理结果
        """
        captcha_type = captcha_data.get("type")
        if not captcha_type:
            return {
                "success": False,
                "message": "未指定验证码类型"
            }
        
        handler = self.handlers.get(captcha_type)
        if not handler:
            # 如果没有对应的处理器，则转发给人工处理
            logger.warning(f"未找到处理器: {captcha_type}，转发给人工处理")
            return await self.handlers["human"].solve(captcha_data)
        
        try:
            result = await handler.solve(captcha_data)
            
            # 如果处理失败且需要人工干预，则转发给人工处理
            if not result.get("success") and result.get("human_intervention_needed"):
                logger.info(f"验证码处理失败，转发给人工处理: {captcha_type}")
                return await self.handlers["human"].solve(captcha_data)
                
            return result
        except Exception as e:
            logger.error(f"验证码处理异常: {str(e)}")
            # 发生异常时，转发给人工处理
            return await self.handlers["human"].solve(captcha_data)
    
    def get_pending_captchas(self) -> List[Dict[str, Any]]:
        """
        获取待处理的验证码列表
        
        Returns:
            待处理验证码列表
        """
        return self.human_intervention.get_pending_captchas()
    
    def submit_result(self, captcha_id: str, result: Dict[str, Any]) -> bool:
        """
        提交人工干预结果
        
        Args:
            captcha_id: 验证码ID
            result: 处理结果
            
        Returns:
            是否成功提交
        """
        return self.human_intervention.submit_result(captcha_id, result)
    
    @staticmethod
    def image_to_base64(image_data: bytes) -> str:
        """
        将图片数据转换为base64编码
        
        Args:
            image_data: 图片数据
            
        Returns:
            base64编码的字符串
        """
        return base64.b64encode(image_data).decode('utf-8')
    
    @staticmethod
    def base64_to_image(base64_data: str) -> bytes:
        """
        将base64编码转换为图片数据
        
        Args:
            base64_data: base64编码的字符串
            
        Returns:
            图片数据
        """
        return base64.b64decode(base64_data)