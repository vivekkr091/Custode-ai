"""Application configuration settings."""

from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CUSTODE platform application settings."""

    # Project metadata
    PROJECT_NAME: str = "CUSTODE"
    SERVICE_NAME: str = "custode-api"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # API routing
    API_V1_PREFIX: str = "/api/v1"

    # CORS — override via CORS_ORIGINS env var (JSON list string)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Database ---
    # For production, set via DATABASE_URL environment variable.
    # Tests override this with an aiosqlite URL.
    DATABASE_URL: str = (
        "postgresql+asyncpg://custode:custode_dev_password@localhost:5432/custode"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # --- Security & Cryptography ---
    # MUST be changed in production. No secrets should live in source.
    SECRET_KEY: str = "dev-secret-key-please-change-in-production-min-32-chars"

    # --- Human User Authentication (Milestone 14) ---
    AUTH_MODE: str = "development"  # "development" | "production"
    AUTH_SECRET_KEY: str = "dev-auth-jwt-secret-key-please-change-in-production-min-32-chars"
    AUTH_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_ISSUER: str = "custode-auth"
    AUTH_AUDIENCE: str = "custode-control-plane"

    # --- Demo / Seeder Mode ---
    DEMO_MODE: bool = False

    # --- Resource & Ingress Bounds (Milestone 22 Hardening) ---
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024  # 10 MB default limit

    # --- Reverse Proxy & Networking (Milestone 23 DevOps) ---
    FORWARDED_ALLOW_IPS: str = "*"
    TRUSTED_PROXIES: List[str] = [
        "127.0.0.1",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Strict validation ensuring production deployments never use insecure defaults."""
        env = self.ENVIRONMENT.lower().strip()
        if env in ("production", "prod", "staging"):
            # 1. Insecure default secret keys
            dev_secret = "dev-secret-key-please-change-in-production-min-32-chars"
            if self.SECRET_KEY == dev_secret or "dev-secret" in self.SECRET_KEY:
                raise ValueError(
                    "Insecure default SECRET_KEY rejected in production environment. "
                    "Provide a cryptographically random secret with at least 32 characters."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters long in production.")

            # 2. Insecure default auth secret key
            dev_auth_secret = "dev-auth-jwt-secret-key-please-change-in-production-min-32-chars"
            if self.AUTH_SECRET_KEY == dev_auth_secret or "dev-auth" in self.AUTH_SECRET_KEY:
                raise ValueError(
                    "Insecure default AUTH_SECRET_KEY rejected in production environment. "
                    "Provide a cryptographically random secret with at least 32 characters."
                )
            if len(self.AUTH_SECRET_KEY) < 32:
                raise ValueError("AUTH_SECRET_KEY must be at least 32 characters long in production.")

            # 3. DEBUG mode must be disabled
            if self.DEBUG:
                raise ValueError("DEBUG mode must be set to False in production environment.")

            # 4. Auth mode must be production
            if self.AUTH_MODE == "development":
                raise ValueError("AUTH_MODE cannot be 'development' in production. Set AUTH_MODE='production'.")

            # 5. Demo mode must be disabled
            if self.DEMO_MODE:
                raise ValueError("DEMO_MODE cannot be enabled in production environment.")

            # 6. Database URL must not use dev default credentials
            if "custode_dev_password" in self.DATABASE_URL:
                raise ValueError(
                    "Default development credentials detected in production DATABASE_URL. "
                    "Provide production database credentials."
                )

        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
