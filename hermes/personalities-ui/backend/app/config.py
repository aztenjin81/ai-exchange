"""Application configuration from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Pydantic settings loaded from env vars (and .env if present)."""

    # Path where personality configs, MCP configs, etc. are stored
    data_path: Path = Path("/app/data")

    # Hermes config directory (mounted from host)
    hermes_config_dir: Path = Path("/root/.hermes")

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
    ]

    # Encryption key path for provider API keys
    encryption_key_path: Path = Path("/app/data/keys/fernet.key")

    # Logging
    log_level: str = "info"

    model_config = {"env_prefix": "PERSONALITIES_UI_", "env_file": ".env"}
