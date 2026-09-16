"""Validated, local configuration; never loads credentials into public responses."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRAVEL_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )
    data_mode: Literal["fixture", "live"] = "fixture"
    model_provider: Literal["disabled", "openai", "gemini"] = "disabled"
    model_name: str = ""
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    model_max_calls: int = Field(default=0, ge=0, le=100)
    serpapi_api_key: SecretStr | None = None
    hotel_max_calls: int = Field(default=0, ge=0, le=10)

    @property
    def hotels_available(self) -> bool:
        return bool(self.data_mode == "live" and self.serpapi_api_key
                    and self.serpapi_api_key.get_secret_value().strip() and self.hotel_max_calls > 0)

    @property
    def chat_available(self) -> bool:
        key = self.openai_api_key if self.model_provider == "openai" else self.gemini_api_key
        return bool(self.model_provider != "disabled" and self.model_name.strip()
                    and key and key.get_secret_value().strip()
                    and self.model_max_calls > 0)
