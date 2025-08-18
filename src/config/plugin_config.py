"""Plugin configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any

from settings import PROJECT_ROOT


@dataclass
class PluginConfig:
    """Plugin system configuration.
    
    Attributes:
        plugins_dir: Directory containing plugin modules
        enabled_plugins: List of enabled plugin names
        disabled_plugins: List of disabled plugin names
        plugin_settings: Plugin-specific settings
        auto_discover: Whether to auto-discover plugins
        reload_on_change: Whether to reload plugins when files change
        max_concurrent_plugins: Maximum number of concurrent plugin instances
    """
    
    plugins_dir: Path = field(default_factory=lambda: Path(os.getenv(
        "PLUGINS_DIR", 
        str(PROJECT_ROOT / "src" / "plugins")
    )))
    enabled_plugins: List[str] = field(default_factory=lambda: [
        plugin.strip() for plugin in os.getenv("ENABLED_PLUGINS", "xiaohongshu_v2").split(",")
        if plugin.strip()
    ])
    disabled_plugins: List[str] = field(default_factory=lambda: [
        plugin.strip() for plugin in os.getenv("DISABLED_PLUGINS", "").split(",")
        if plugin.strip()
    ])
    plugin_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    auto_discover: bool = field(default_factory=lambda: os.getenv("PLUGIN_AUTO_DISCOVER", "true").lower() == "true")
    reload_on_change: bool = field(default_factory=lambda: os.getenv("PLUGIN_RELOAD_ON_CHANGE", "false").lower() == "true")
    max_concurrent_plugins: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_PLUGINS", "5")))
    
    def __post_init__(self) -> None:
        """Ensure plugins directory exists and is absolute."""
        if not self.plugins_dir.is_absolute():
            self.plugins_dir = PROJECT_ROOT / self.plugins_dir
        
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if a plugin is enabled.
        
        Args:
            plugin_name: Name of the plugin to check
            
        Returns:
            True if plugin is enabled, False otherwise
        """
        if plugin_name in self.disabled_plugins:
            return False
        
        if not self.enabled_plugins:  # If no specific plugins enabled, enable all
            return True
        
        return plugin_name in self.enabled_plugins
    
    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """Get settings for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin-specific settings dictionary
        """
        return self.plugin_settings.get(plugin_name, {})
    
    def set_plugin_settings(self, plugin_name: str, settings: Dict[str, Any]) -> None:
        """Set settings for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            settings: Settings dictionary to set
        """
        self.plugin_settings[plugin_name] = settings
    
    def add_enabled_plugin(self, plugin_name: str) -> None:
        """Add a plugin to the enabled list.
        
        Args:
            plugin_name: Name of the plugin to enable
        """
        if plugin_name not in self.enabled_plugins:
            self.enabled_plugins.append(plugin_name)
        
        # Remove from disabled list if present
        if plugin_name in self.disabled_plugins:
            self.disabled_plugins.remove(plugin_name)
    
    def add_disabled_plugin(self, plugin_name: str) -> None:
        """Add a plugin to the disabled list.
        
        Args:
            plugin_name: Name of the plugin to disable
        """
        if plugin_name not in self.disabled_plugins:
            self.disabled_plugins.append(plugin_name)
        
        # Remove from enabled list if present
        if plugin_name in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name)