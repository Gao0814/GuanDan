"""Centralized environment configuration loader for phase-1."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Application runtime config from environment variables."""

    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    deepseek_enabled: bool
    deepseek_timeout: float
    deepseek_max_retries: int
    debug: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        # Load repository-root .env explicitly so `python -m ...` reads local secrets/config.
        load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"), override=False)
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_enabled=_parse_bool(os.getenv("DEEPSEEK_ENABLED"), default=False),
            deepseek_timeout=float(os.getenv("DEEPSEEK_TIMEOUT", "30")),
            deepseek_max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "1")),
            debug=_parse_bool(os.getenv("DEBUG"), default=True),
        )
