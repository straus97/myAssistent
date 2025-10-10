from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import os

# Если используешь python-dotenv — подхватит .env автоматически
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings:
    ENV: str
    API_BASE_URL: str
    DATABASE_URL: str
    USE_PGBOUNCER: bool
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int
    DB_POOL_RECYCLE: int
    LOG_DIR: Path
    ARTIFACTS_DIR: Path
    TELEGRAM_BOT_TOKEN: str | None
    TELEGRAM_CHAT_ID: str | None
    NEWS_API_KEY: str | None
    BYBIT_API_KEY: str | None
    BYBIT_API_SECRET: str | None
    API_KEY: str | None

    def __init__(self):
        self.ENV = os.getenv("ENV", "dev")
        self.API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        
        # Database URL: поддержка SQLite и PostgreSQL
        # SQLite (по умолчанию): sqlite:///assistant.db
        # PostgreSQL: postgresql://user:pass@localhost:5432/myassistent
        # PostgreSQL + pgbouncer: postgresql://user:pass@localhost:6432/myassistent
        default_db_url = f"sqlite:///{PROJECT_ROOT/'assistant.db'}"
        self.DATABASE_URL = os.getenv("DATABASE_URL", default_db_url)
        
        # PostgreSQL connection pooling настройки
        self.USE_PGBOUNCER = os.getenv("USE_PGBOUNCER", "false").lower() == "true"
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
        self.DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 час
        
        self.LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "logs"))
        self.ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", PROJECT_ROOT / "artifacts"))
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or None
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or None
        self.NEWS_API_KEY = os.getenv("NEWS_API_KEY") or None
        self.BYBIT_API_KEY = os.getenv("BYBIT_API_KEY") or None
        self.BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET") or None
        self.API_KEY = os.getenv("API_KEY") or None

        # гарантируем существование папок
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_postgres(self) -> bool:
        """Проверка, используется ли PostgreSQL"""
        return self.DATABASE_URL.startswith("postgresql")
    
    @property
    def is_sqlite(self) -> bool:
        """Проверка, используется ли SQLite"""
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Удобный единый импорт
settings = get_settings()
