"""Runtime configuration.

Settings are read from environment variables prefixed with ``LEDGERLINE_``
or from a ``.env`` file in the current working directory. All values have
sensible defaults so the server can boot with zero configuration on a
fresh machine.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ledgerline server settings."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERLINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server -------------------------------------------------------------
    host: str = Field(default="127.0.0.1", description="Bind address.")
    port: int = Field(default=8787, description="HTTP port.")
    dev_mode: bool = Field(
        default=False,
        description="Enables hot-reload and permissive CORS. Never on in prod.",
    )

    # --- Data ---------------------------------------------------------------
    data_dir: Path = Field(
        default=Path.home() / ".ledgerline",
        description=(
            "Root directory for all Ledgerline data: the registry database "
            "and per-company SQLite files."
        ),
    )

    # --- API ----------------------------------------------------------------
    api_prefix: str = Field(default="/api/v1", description="API URL prefix.")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        description="CORS allow-list. Frontend dev server by default.",
    )

    def registry_db_path(self) -> Path:
        """SQLite file that tracks companies and their on-disk databases."""
        return self.data_dir / "registry.db"

    def company_db_path(self, company_id: str) -> Path:
        """Return the SQLite path for a given company id."""
        return self.data_dir / "companies" / f"{company_id}.db"

    def ensure_directories(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "companies").mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached settings instance. Safe to call at import time."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
