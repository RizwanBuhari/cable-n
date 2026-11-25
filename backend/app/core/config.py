"""Settings, read from backend/.env (see backend/.env.example).

Cable-N is a public, stateless website: no accounts and no database. The
server keeps nothing about a visitor's calculations - inputs arrive with
each request, results are computed, returned and forgotten. Reports are
built in a temporary directory that is deleted immediately afterwards.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / '.env'), extra='ignore')

    APP_NAME: str = 'Cable-N'
    APP_ENV: str = 'development'          # development | production
    ALLOWED_ORIGINS: str = 'http://localhost:5173,http://127.0.0.1:5173'
    TRUST_PROXY_HEADERS: bool = False     # true only behind a reverse proxy you control

    # --- public-API protection -------------------------------------------
    MAX_BODY_KB: int = 512                # JSON request bodies
    MAX_UPLOAD_MB: int = 8                # Excel imports / datasheet PDFs
    CALC_RATE_PER_MINUTE: int = 60        # per client IP
    REPORT_RATE_PER_MINUTE: int = 6
    VALIDATION_RATE_PER_MINUTE: int = 4
    ENGINE_TIMEOUT_S: float = 20.0        # per request, see docs/KNOWN_LIMITATIONS.md
    ENGINE_MAX_CONCURRENT: int = 4        # queued engine requests before "busy"
    BATCH_MAX_FEEDERS: int = 200
    SWEEP_MAX_POINTS: int = 15

    # --- optional AI assistant -------------------------------------------
    AI_ENABLED: bool = False
    AI_PROVIDER: str = 'gemini'
    GEMINI_API_KEY: str = ''
    GEMINI_MODEL: str = 'gemini-3.1-flash-lite'
    AI_RATE_PER_MINUTE: int = 3           # per IP
    AI_DAILY_PER_IP: int = 20
    AI_DAILY_GLOBAL: int = 500            # hard ceiling on provider calls per day

    # --- optional ad-free licence keys (future premium tier) -------------
    PREMIUM_SECRET: str = ''              # empty = feature off

    LOGO_PATH: str = str(PROJECT_DIR / 'frontend' / 'public' / 'brand' / 'cable-n-logo.png')

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(',') if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == 'production'

    @property
    def ai_configured(self) -> bool:
        return self.AI_ENABLED and bool(self.GEMINI_API_KEY) and self.AI_PROVIDER == 'gemini'


@lru_cache
def get_settings() -> Settings:
    return Settings()
