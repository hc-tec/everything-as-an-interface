"""Browser configuration management."""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ViewportConfig:
    """Browser viewport configuration.
    
    Attributes:
        width: Viewport width in pixels
        height: Viewport height in pixels
    """
    
    width: int = field(default_factory=lambda: int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280")))
    height: int = field(default_factory=lambda: int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "800")))
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format for Playwright."""
        return {"width": self.width, "height": self.height}


@dataclass
class ProxyConfig:
    """Browser proxy configuration.
    
    Attributes:
        server: Proxy server URL
        username: Proxy username
        password: Proxy password
        bypass: Comma-separated list of hosts to bypass proxy
    """
    
    server: Optional[str] = field(default_factory=lambda: os.getenv("PROXY_SERVER"))
    username: Optional[str] = field(default_factory=lambda: os.getenv("PROXY_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("PROXY_PASSWORD"))
    bypass: Optional[str] = field(default_factory=lambda: os.getenv("PROXY_BYPASS"))
    
    def to_dict(self) -> Optional[Dict[str, Any]]:
        """Convert to dictionary format for Playwright."""
        if not self.server:
            return None
        
        proxy_dict = {"server": self.server}
        if self.username:
            proxy_dict["username"] = self.username
        if self.password:
            proxy_dict["password"] = self.password
        if self.bypass:
            proxy_dict["bypass"] = self.bypass
        
        return proxy_dict


@dataclass
class BrowserConfig:
    """Browser automation configuration.
    
    Attributes:
        channel: Browser channel (chrome, msedge, etc.)
        headless: Whether to run browser in headless mode
        viewport: Viewport configuration
        user_agent: Custom user agent string
        proxy: Proxy configuration
        timeout_ms: Default timeout in milliseconds
        slow_mo_ms: Slow motion delay in milliseconds
        devtools: Whether to open devtools
        downloads_path: Path for downloads
        extra_http_headers: Additional HTTP headers
    """
    
    channel: str = field(default_factory=lambda: os.getenv("BROWSER_CHANNEL", "msedge"))
    headless: bool = field(default_factory=lambda: os.getenv("BROWSER_HEADLESS", "false").lower() == "true")
    viewport: ViewportConfig = field(default_factory=ViewportConfig)
    user_agent: Optional[str] = field(default_factory=lambda: os.getenv(
        "BROWSER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ))
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    timeout_ms: int = field(default_factory=lambda: int(os.getenv("BROWSER_TIMEOUT_MS", "30000")))
    slow_mo_ms: int = field(default_factory=lambda: int(os.getenv("BROWSER_SLOW_MO_MS", "0")))
    devtools: bool = field(default_factory=lambda: os.getenv("BROWSER_DEVTOOLS", "false").lower() == "true")
    downloads_path: Optional[str] = field(default_factory=lambda: os.getenv("BROWSER_DOWNLOADS_PATH"))
    extra_http_headers: Dict[str, str] = field(default_factory=dict)
    
    def get_launch_options(self) -> Dict[str, Any]:
        """Get browser launch options for Playwright."""
        options = {
            "headless": self.headless,
            "channel": self.channel,
            "timeout": self.timeout_ms,
        }
        
        if self.slow_mo_ms > 0:
            options["slow_mo"] = self.slow_mo_ms
        
        if self.devtools:
            options["devtools"] = self.devtools
        
        if self.downloads_path:
            options["downloads_path"] = self.downloads_path
        
        proxy_dict = self.proxy.to_dict()
        if proxy_dict:
            options["proxy"] = proxy_dict
        
        return options
    
    def get_context_options(self) -> Dict[str, Any]:
        """Get browser context options for Playwright."""
        options = {
            "viewport": self.viewport.to_dict(),
        }
        
        if self.user_agent:
            options["user_agent"] = self.user_agent
        
        if self.extra_http_headers:
            options["extra_http_headers"] = self.extra_http_headers
        
        return options