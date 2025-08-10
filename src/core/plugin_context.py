from dataclasses import dataclass
from typing import Any, Optional, Dict
from playwright.async_api import Page, BrowserContext
from .account_manager import AccountManager

@dataclass(frozen=True)
class PluginContext:
    page: Page
    browser_context: BrowserContext
    account_manager: AccountManager
    storage: Optional[Any]
    event_bus: Optional[Any]
    logger: Any
    settings: Dict[str, Any] 