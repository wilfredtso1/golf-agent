from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    twilio_validate_signature: bool
    sms_send_enabled: bool
    openai_api_key: str
    openai_model: str
    tee_time_provider: str
    default_timezone: str
    form_token_secret: str
    form_token_ttl_seconds: int
    form_base_url: str
    cors_allow_origins: tuple[str, ...]
    golfnow_scrape_timeout_ms: int
    golfnow_scrape_headless: bool


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SETTINGS = Settings(
    database_url=_required_env("DATABASE_URL"),
    twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
    twilio_auth_token=_required_env("TWILIO_AUTH_TOKEN"),
    twilio_phone_number=_required_env("TWILIO_PHONE_NUMBER"),
    twilio_validate_signature=_bool_env("TWILIO_VALIDATE_SIGNATURE", True),
    sms_send_enabled=_bool_env("SMS_SEND_ENABLED", False),
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    tee_time_provider=os.getenv("TEE_TIME_PROVIDER", "mock").strip().lower(),
    default_timezone=os.getenv("DEFAULT_TIMEZONE", "America/New_York"),
    form_token_secret=_required_env("FORM_TOKEN_SECRET"),
    form_token_ttl_seconds=int(os.getenv("FORM_TOKEN_TTL_SECONDS", "604800")),
    form_base_url=os.getenv("FORM_BASE_URL", "http://127.0.0.1:5173/golf-form"),
    cors_allow_origins=_csv_env("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
    golfnow_scrape_timeout_ms=int(os.getenv("GOLFNOW_SCRAPE_TIMEOUT_MS", "20000")),
    golfnow_scrape_headless=_bool_env("GOLFNOW_SCRAPE_HEADLESS", True),
)
