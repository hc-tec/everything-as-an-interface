"""Webhook configuration management."""

import os
from dataclasses import dataclass, field


@dataclass
class WebhookConfig:
    """Webhook dispatcher configuration.

    Attributes:
        concurrency: Number of concurrent webhook workers
        request_timeout_sec: Timeout for webhook HTTP requests in seconds
        max_chunk_size_bytes: Maximum size of each webhook payload chunk in bytes
        max_retries: Maximum retry attempts for failed webhooks
    """

    concurrency: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_CONCURRENCY", "4")))
    request_timeout_sec: float = field(default_factory=lambda: float(os.getenv("WEBHOOK_TIMEOUT_SEC", "100.0")))
    max_chunk_size_bytes: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_MAX_CHUNK_SIZE", "800000")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_MAX_RETRIES", "5")))

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.concurrency < 1:
            raise ValueError("webhook concurrency must be at least 1")
        if self.request_timeout_sec <= 0:
            raise ValueError("webhook request timeout must be greater than 0")
        if self.max_chunk_size_bytes < 1024:
            raise ValueError("webhook max chunk size must be at least 1024 bytes")
        if self.max_retries < 0:
            raise ValueError("webhook max retries cannot be negative")
