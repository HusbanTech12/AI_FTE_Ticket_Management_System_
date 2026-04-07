"""
Centralized configuration management for Customer Success FTE.

All environment variables and configuration constants in one place.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables."""

    # Database
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://fte:fte_password@localhost:5432/fte_db"
    ))

    # Kafka
    kafka_bootstrap_servers: str = field(default_factory=lambda: os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092"
    ))

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))

    # Gmail
    gmail_credentials_path: Optional[str] = field(
        default_factory=lambda: os.getenv("GMAIL_CREDENTIALS_PATH", "") or None
    )
    gmail_user_email: Optional[str] = field(
        default_factory=lambda: os.getenv("GMAIL_USER_EMAIL", "") or None
    )

    # Twilio/WhatsApp
    twilio_account_sid: Optional[str] = field(
        default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", "") or None
    )
    twilio_auth_token: Optional[str] = field(
        default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", "") or None
    )
    twilio_whatsapp_number: Optional[str] = field(
        default_factory=lambda: os.getenv("TWILIO_WHATSAPP_NUMBER", "") or None
    )

    # API
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    allowed_origins: str = field(default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "*"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Security
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "insecure-dev-key"))

    def validate(self) -> list[str]:
        """Validate required configuration. Returns list of missing required fields."""
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.kafka_bootstrap_servers:
            missing.append("KAFKA_BOOTSTRAP_SERVERS")
        return missing


# Global config instance
config = AppConfig()

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def validate_config():
    """Validate all required configuration and exit if missing."""
    missing = config.validate()
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    return config


validate_config()
