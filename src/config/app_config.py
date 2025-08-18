"""Application configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from settings import PROJECT_ROOT


@dataclass
class AppConfig:
    """Main application configuration.
    
    Attributes:
        project_root: Project root directory path
        master_key: Encryption key for sensitive data
        accounts_path: Path to accounts storage directory
        data_path: Path to data storage directory
        log_level: Logging level
        debug: Debug mode flag
        environment: Application environment (dev, test, prod)
    """
    
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    master_key: str = field(default_factory=lambda: os.getenv("APP_MASTER_KEY", "default-dev-key"))
    accounts_path: Path = field(default_factory=lambda: Path("./accounts"))
    data_path: Path = field(default_factory=lambda: Path("./data"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    
    def __post_init__(self) -> None:
        """Ensure paths are absolute and directories exist."""
        if not self.accounts_path.is_absolute():
            self.accounts_path = self.project_root / self.accounts_path
        if not self.data_path.is_absolute():
            self.data_path = self.project_root / self.data_path
            
        # Create directories if they don't exist
        self.accounts_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"