from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/dshop"

    # App
    SECRET_KEY: str = "change_me"

    # Telegram
    TELEGRAM_TOKEN: Optional[str] = None

    # Wildberries
    WB_API_KEY: Optional[str] = None

    # Al-Style.kz
    ALSTYLE_TOKEN: Optional[str] = None
    ALSTYLE_BASE_URL: str = "https://api.al-style.kz"
    ALSTYLE_TIMEOUT: int = 30
    ALSTYLE_PAGE_SIZE: int = 100
    ALSTYLE_DOWNLOAD_IMAGES: bool = False


settings = Settings()
