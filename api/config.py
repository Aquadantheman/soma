"""API configuration.

Security-first configuration with explicit secret requirements.
"""

import os
import warnings
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment.

    Security Notes:
    - database_url must be explicitly configured (no hardcoded credentials)
    - redis_url and redis_password are optional but recommended
    - debug mode is off by default
    - In production, ensure SOMA_DEBUG=false
    """

    # Database - NO hardcoded defaults for security
    database_url: Optional[str] = None

    # Redis (optional caching)
    redis_url: Optional[str] = None
    redis_password: Optional[str] = None

    # API metadata
    api_title: str = "Soma API"
    api_version: str = "0.1.0"

    # Debug mode - MUST be false in production
    debug: bool = False

    # Authentication mode (handled by auth module, but declared here to allow env var)
    auth_mode: str = "api_key"

    # OAuth2 - Whoop Integration
    whoop_client_id: Optional[str] = None
    whoop_client_secret: Optional[str] = None
    whoop_redirect_uri: str = "http://localhost:8000/v1/oauth/callback/whoop"

    class Config:
        env_file = ".env"
        env_prefix = "SOMA_"

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v: Optional[str]) -> str:
        """Validate database URL is configured."""
        if v is None:
            # Check if running in development mode
            if os.getenv("SOMA_DEBUG", "false").lower() == "true":
                warnings.warn(
                    "SOMA_DATABASE_URL not set. Using development default. "
                    "DO NOT use this in production!",
                    UserWarning
                )
                return "postgresql+psycopg2://soma:soma_dev@127.0.0.1:5432/soma"
            else:
                raise ValueError(
                    "SOMA_DATABASE_URL must be set. "
                    "Set SOMA_DEBUG=true for development defaults."
                )

        # Warn if using default development password
        if "soma_dev" in v:
            warnings.warn(
                "Database URL contains development password 'soma_dev'. "
                "Use a strong password in production!",
                UserWarning
            )

        return v

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug

    def validate_production_config(self) -> list[str]:
        """Validate configuration for production use.

        Returns list of warnings/errors for production deployment.
        """
        issues = []

        if self.debug:
            issues.append("DEBUG mode is enabled - disable for production")

        if self.database_url and "soma_dev" in self.database_url:
            issues.append("Using development database password")

        if self.redis_url and not self.redis_password:
            issues.append("Redis password not set")

        return issues


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()

    # Log production warnings
    if not settings.debug:
        issues = settings.validate_production_config()
        if issues:
            import logging
            logger = logging.getLogger("soma.config")
            for issue in issues:
                logger.warning(f"Production config issue: {issue}")

    return settings
