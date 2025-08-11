import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Mapping

from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig

logger = logging.getLogger("plugin")

class BasePlugin(ABC):
    """
    插件基类：所有自动化接口插件都需继承此类
    
    插件生命周期：
    1. 初始化（__init__）
    2. 配置（configure）
    3. 启动（start）
    4. 执行/轮询（fetch/poll）
    5. 停止（stop）
    """
    
    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = ""
    # 插件名称
    PLUGIN_NAME: str = ""
    # 插件描述
    PLUGIN_DESCRIPTION: str = ""
    # 插件版本
    PLUGIN_VERSION: str = "0.1.0"
    # 插件作者
    PLUGIN_AUTHOR: str = ""
    
    def __init__(self):
        self.config: Optional[TaskConfig] = None
        self.running: bool = False
        self.accounts: List[Dict[str, Any]] = []
        self.selected_account: Optional[Dict[str, Any]] = None
        self._last_data: Any = None
        self.input_data: Dict[str, Any] = {}
        # 注入的 Playwright Page（或等价对象）
        self.page: Optional[Any] = None
        # 注入的运行上下文（可选）
        self.ctx: Optional[PluginContext] = None
        self.account_manager = None
    
    def configure(self, config: TaskConfig) -> None:
        """
        配置插件
        
        Args:
            config: 插件配置
        """
        self.config = config
        logger.info(f"插件 {self.PLUGIN_ID} 已配置")
    
    def set_context(self, ctx: PluginContext) -> None:
        """
        注入外部上下文，内含 page、browser_context、account_manager 等。
        """
        self.ctx = ctx
        self.page = self.ctx.page
        self.account_manager = self.ctx.account_manager
        logger.info(f"插件 {self.PLUGIN_ID} 已注入 Context")
    
    def set_input(self, input_data: Dict[str, Any]) -> None:
        """
        设置本次执行的输入参数（例如文本、链接、图片等）
        
        Args:
            input_data: 输入参数字典
        """
        self.input_data = input_data or {}

    def get_input(self) -> Dict[str, Any]:
        """
        获取已设置的输入参数
        """
        return self.input_data
    
    def set_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        """
        设置可用账号列表
        
        Args:
            accounts: 账号列表
        """
        self.accounts = accounts
    
    def select_account(self, account_id: str) -> bool:
        """
        选择使用的账号
        
        Args:
            account_id: 账号ID
            
        Returns:
            是否成功选择账号
        """
        for account in self.accounts:
            if account.get("id") == account_id:
                self.selected_account = account
                logger.info(f"插件 {self.PLUGIN_ID} 已选择账号: {account_id}")
                return True
        
        logger.error(f"插件 {self.PLUGIN_ID} 选择账号失败: 账号 {account_id} 不存在")
        return False
    
    @abstractmethod
    def start(self) -> bool:
        """
        启动插件
        
        Returns:
            是否成功启动
        """
        self.running = True
        logger.info(f"插件 {self.PLUGIN_ID} 已启动")
        return True
    
    @abstractmethod
    def stop(self) -> bool:
        """
        停止插件
        
        Returns:
            是否成功停止
        """
        self.running = False
        logger.info(f"插件 {self.PLUGIN_ID} 已停止")
        return True
    
    @abstractmethod
    async def fetch(self) -> Dict[str, Any]:
        """
        获取数据
        
        Returns:
            获取到的数据
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取插件元数据
        
        Returns:
            插件元数据
        """
        return {
            "id": self.PLUGIN_ID,
            "name": self.PLUGIN_NAME,
            "description": self.PLUGIN_DESCRIPTION,
            "version": self.PLUGIN_VERSION,
            "author": self.PLUGIN_AUTHOR,
        }
    
    def needs_account(self) -> bool:
        """
        是否需要账号
        
        Returns:
            是否需要账号
        """
        return True
    
    def handle_captcha(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理验证码
        
        Args:
            captcha_data: 验证码数据
            
        Returns:
            处理结果
        """
        # 默认实现，子类可覆盖
        return {"success": False, "message": "未实现验证码处理"}
    
    def validate_config(self, config: TaskConfig) -> Dict[str, Any]:
        """
        验证配置是否合法
        
        Args:
            config: 配置数据
            
        Returns:
            验证结果，包含是否成功和错误信息
        """
        # 默认实现，子类应当覆盖
        return {"valid": True, "errors": []} 