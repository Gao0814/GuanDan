"""Centralized environment configuration loader for phase-1."""

from dataclasses import dataclass
import os


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
    debug: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            debug=_parse_bool(os.getenv("DEBUG"), default=True),
        )
