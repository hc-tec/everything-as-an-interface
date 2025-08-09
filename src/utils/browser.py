import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Request, Response

from .network_capture import NetworkRule

logger = logging.getLogger("browser")

class BrowserAutomation:
    """浏览器自动化工具类"""
    
    def __init__(self, headless: bool = True, proxy: Optional[Dict[str, str]] = None):
        """
        初始化浏览器自动化工具
        
        Args:
            headless: 是否以无头模式运行浏览器
            proxy: 代理配置，格式为 {"server": "http://proxy-server.com:8080", "username": "user", "password": "pass"}
        """
        self.headless = headless
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Network capture extensions
        self._network_rules: Dict[str, NetworkRule] = {}
        self._network_events: List[Dict[str, Any]] = []
    
    async def __aenter__(self):
        """
        异步上下文管理器入口，自动启动浏览器
        """
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出，自动关闭浏览器
        """
        await self.close()
        
    async def start(self) -> None:
        """
        启动浏览器
        """
        playwright = await async_playwright().start()
        
        # 创建浏览器实例
        launch_args = {
            "headless": self.headless,
        }
        
        self.browser = await playwright.chromium.launch(**launch_args)
        
        # 创建浏览器上下文
        context_args = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        }
        
        if self.proxy:
            context_args["proxy"] = self.proxy
            
        self.context = await self.browser.new_context(**context_args)
        
        # 创建新页面
        self.page = await self.context.new_page()
        
        # 设置默认超时
        self.page.set_default_timeout(30000)
        
        # 配置请求拦截器（保持可覆盖性）
        await self.context.route("**/*", self._route_handler)

        # Attach network listeners
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)
        
        logger.info("浏览器已启动")
    
    async def _route_handler(self, route, request):
        """
        请求拦截器，用于过滤、修改请求等
        """
        # 默认放行所有请求，子类可以覆盖此方法实现自定义拦截
        await route.continue_()
    
    async def close(self) -> None:
        """
        关闭浏览器
        """
        # detach listeners to avoid memory leaks
        try:
            if self.page:
                self.page.off("request", self._on_request)
                self.page.off("response", self._on_response)
        except Exception:
            pass
        
        if self.context:
            await self.context.close()
            self.context = None
            
        if self.browser:
            await self.browser.close()
            self.browser = None
            
        logger.info("浏览器已关闭")
    
    async def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        """
        导航到指定URL
        
        Args:
            url: 目标URL
            wait_until: 导航完成的等待条件，可选值："domcontentloaded", "load", "networkidle"
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        logger.info(f"导航到: {url}")
        await self.page.goto(url, wait_until=wait_until)
    
    async def screenshot(self, path: str) -> None:
        """
        截取当前页面截图
        
        Args:
            path: 保存路径
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        await self.page.screenshot(path=path)
        logger.info(f"截图已保存至: {path}")
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> Optional[Any]:
        """
        等待指定元素出现
        
        Args:
            selector: CSS选择器
            timeout: 超时时间(ms)
            
        Returns:
            找到的元素，未找到则返回None
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            return element
        except Exception as e:
            logger.error(f"等待元素 {selector} 失败: {str(e)}")
            return None
    
    async def click(self, selector: str, timeout: int = 30000) -> bool:
        """
        点击指定元素
        
        Args:
            selector: CSS选择器
            timeout: 超时时间(ms)
            
        Returns:
            是否成功点击
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        try:
            await self.page.click(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"点击元素 {selector} 失败: {str(e)}")
            return False
    
    async def fill(self, selector: str, value: str, timeout: int = 30000) -> bool:
        """
        填充输入框
        
        Args:
            selector: CSS选择器
            value: 输入值
            timeout: 超时时间(ms)
            
        Returns:
            是否成功填充
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        try:
            await self.page.fill(selector, value, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"填充元素 {selector} 失败: {str(e)}")
            return False
    
    async def evaluate(self, expression: str) -> Any:
        """
        在页面上下文中执行JavaScript表达式
        
        Args:
            expression: JavaScript表达式
            
        Returns:
            表达式执行结果
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")
            
        try:
            return await self.page.evaluate(expression)
        except Exception as e:
            logger.error(f"执行JavaScript失败: {str(e)}")
            return None
    
    async def get_cookies(self) -> List[Dict[str, Any]]:
        """
        获取当前页面的Cookie
        
        Returns:
            Cookie列表
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")
            
        return await self.context.cookies()
    
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """
        设置Cookie
        
        Args:
            cookies: Cookie列表
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")
            
        await self.context.add_cookies(cookies)
    
    async def handle_captcha(self, captcha_handler: Optional[Callable] = None) -> Dict[str, Any]:
        """
        处理验证码
        
        Args:
            captcha_handler: 自定义验证码处理函数
            
        Returns:
            处理结果
        """
        # 这里是一个通用的验证码处理逻辑，实际应用需要针对具体情况开发
        # 如果提供了自定义处理函数，则调用它
        if captcha_handler:
            return await captcha_handler(self.page)
        
        # 默认实现：截图验证码并返回
        try:
            # 假设验证码在一个特定元素内
            captcha_elem = await self.wait_for_selector("#captcha")
            if not captcha_elem:
                return {"success": False, "message": "未找到验证码元素"}
                
            # 截取验证码图片
            captcha_screenshot = await captcha_elem.screenshot()
            
            return {
                "success": True,
                "type": "image",
                "data": captcha_screenshot,
                "message": "需要人工处理验证码"
            }
        except Exception as e:
            logger.error(f"处理验证码失败: {str(e)}")
            return {"success": False, "message": str(e)}

    # ---------------------
    # Network capture APIs
    # ---------------------
    def register_network_rule(self, rule: NetworkRule) -> None:
        """注册一条网络请求/响应规则。"""
        self._network_rules[rule.rule_id] = rule

    def remove_network_rule(self, rule_id: str) -> bool:
        """移除规则。"""
        return self._network_rules.pop(rule_id, None) is not None

    def clear_network_rules(self) -> None:
        """清空所有规则。"""
        self._network_rules.clear()

    def get_network_rules(self) -> List[NetworkRule]:
        """获取当前注册的规则列表。"""
        return list(self._network_rules.values())

    def get_captured_network_events(self, clear: bool = False) -> List[Dict[str, Any]]:
        """获取捕获到的网络事件结果，可选清空缓存。"""
        events = list(self._network_events)
        if clear:
            self._network_events.clear()
        return events

    async def _on_request(self, request: Request) -> None:
        await self._dispatch_network(request, kind="request")

    async def _on_response(self, response: Response) -> None:
        await self._dispatch_network(response, kind="response")

    async def _dispatch_network(self, obj: Union[Request, Response], kind: str) -> None:
        # Iterate rules and apply independently
        for rule in list(self._network_rules.values()):
            try:
                if not rule.enabled or rule.kind != kind:
                    continue
                if await rule.matches(obj):
                    processed = await rule.run_process(obj)
                    payload: Dict[str, Any] = {
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "kind": kind,
                        "url": getattr(obj, "url", None),
                        "data": processed,
                    }
                    # Enrich minimal metadata for debug
                    if kind == "request":
                        payload["method"] = getattr(obj, "method", None)
                        try:
                            payload["post_data"] = await obj.post_data()  # type: ignore[attr-defined]
                        except Exception:
                            payload["post_data"] = None
                    else:  # response
                        try:
                            payload["status"] = obj.status
                        except Exception:
                            payload["status"] = None
                    self._network_events.append(payload)
            except Exception as exc:
                logger.debug(f"Network rule '{rule.rule_id}' dispatch error: {exc}") 