"""Loader konfigurasi dari .env dan config/keywords.yaml (PRD bagian 5, 8)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _get_time(env_key: str, default: str) -> time:
    raw = os.getenv(env_key, default)
    hh, mm = raw.split(":")
    return time(int(hh), int(mm))


@dataclass(frozen=True)
class CategoryRule:
    name: str
    label: str
    emoji: str
    keywords: list[str]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_admin_chat_id: str

    poll_page_size: int
    poll_interval_seconds: int
    poll_backoff_max_seconds: int
    poll_max_consecutive_failures: int

    market_open_time: time
    market_close_time: time
    pre_open_check_time: time

    sqlite_db_path: Path
    log_file_path: Path
    log_level: str

    categories: list[CategoryRule] = field(default_factory=list)


def load_keyword_categories(path: Path | None = None) -> list[CategoryRule]:
    path = path or (BASE_DIR / "config" / "keywords.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [
        CategoryRule(
            name=c["name"],
            label=c["label"],
            emoji=c["emoji"],
            keywords=list(c["keywords"]),
        )
        for c in raw["categories"]
    ]


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        telegram_admin_chat_id=os.getenv("TELEGRAM_ADMIN_CHAT_ID", os.environ["TELEGRAM_CHAT_ID"]),
        poll_page_size=int(os.getenv("POLL_PAGE_SIZE", "20")),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "30")),
        poll_backoff_max_seconds=int(os.getenv("POLL_BACKOFF_MAX_SECONDS", "600")),
        poll_max_consecutive_failures=int(os.getenv("POLL_MAX_CONSECUTIVE_FAILURES", "10")),
        market_open_time=_get_time("MARKET_OPEN_TIME", "08:45"),
        market_close_time=_get_time("MARKET_CLOSE_TIME", "16:15"),
        pre_open_check_time=_get_time("PRE_OPEN_CHECK_TIME", "08:30"),
        sqlite_db_path=BASE_DIR / os.getenv("SQLITE_DB_PATH", "data/seen_announcements.sqlite3"),
        log_file_path=BASE_DIR / os.getenv("LOG_FILE_PATH", "logs/idx_alert.log"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        categories=load_keyword_categories(),
    )
