"""Database configuration management."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MongoConfig:
    """MongoDB configuration.
    
    Attributes:
        host: MongoDB host
        port: MongoDB port
        database: Database name
        username: Username for authentication
        password: Password for authentication
        auth_source: Authentication source database
        connection_timeout_ms: Connection timeout in milliseconds
        server_selection_timeout_ms: Server selection timeout in milliseconds
    """
    
    host: str = field(default_factory=lambda: os.getenv("MONGO_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("MONGO_PORT", "27017")))
    database: str = field(default_factory=lambda: os.getenv("MONGO_DATABASE", "everything_interface"))
    username: Optional[str] = field(default_factory=lambda: os.getenv("MONGO_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("MONGO_PASSWORD"))
    auth_source: str = field(default_factory=lambda: os.getenv("MONGO_AUTH_SOURCE", "admin"))
    connection_timeout_ms: int = field(default_factory=lambda: int(os.getenv("MONGO_CONNECTION_TIMEOUT_MS", "5000")))
    server_selection_timeout_ms: int = field(default_factory=lambda: int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")))
    
    @property
    def connection_string(self) -> str:
        """Generate MongoDB connection string."""
        if self.username and self.password:
            auth_part = f"{self.username}:{self.password}@"
        else:
            auth_part = ""
        
        return f"mongodb://{auth_part}{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration.
    
    Attributes:
        host: Redis host
        port: Redis port
        database: Redis database number
        password: Redis password
        connection_timeout_sec: Connection timeout in seconds
        socket_timeout_sec: Socket timeout in seconds
        max_connections: Maximum connections in pool
    """
    
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    database: int = field(default_factory=lambda: int(os.getenv("REDIS_DATABASE", "0")))
    password: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))
    connection_timeout_sec: float = field(default_factory=lambda: float(os.getenv("REDIS_CONNECTION_TIMEOUT_SEC", "5.0")))
    socket_timeout_sec: float = field(default_factory=lambda: float(os.getenv("REDIS_SOCKET_TIMEOUT_SEC", "5.0")))
    max_connections: int = field(default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "10")))


@dataclass
class DatabaseConfig:
    """Combined database configuration.
    
    Attributes:
        mongo: MongoDB configuration
        redis: Redis configuration
        use_mongo: Whether to use MongoDB
        use_redis: Whether to use Redis
    """
    
    mongo: MongoConfig = field(default_factory=MongoConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    use_mongo: bool = field(default_factory=lambda: os.getenv("USE_MONGO", "true").lower() == "true")
    use_redis: bool = field(default_factory=lambda: os.getenv("USE_REDIS", "true").lower() == "true")