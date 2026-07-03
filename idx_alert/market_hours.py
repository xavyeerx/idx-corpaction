"""Penentuan status jam bursa dan jadwal pre-open catch-up (PRD bagian 4, + pre-open alert)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from idx_alert.config import Settings

WIB = pytz.timezone("Asia/Jakarta")

# Senin=0 ... Jumat=4
_TRADING_WEEKDAYS = {0, 1, 2, 3, 4}


def now_wib() -> datetime:
    return datetime.now(WIB)


def is_trading_day(dt: datetime) -> bool:
    return dt.weekday() in _TRADING_WEEKDAYS


def is_market_open(settings: Settings, dt: datetime | None = None) -> bool:
    dt = dt or now_wib()
    if not is_trading_day(dt):
        return False
    return settings.market_open_time <= dt.time() <= settings.market_close_time


def is_pre_open_check_time(settings: Settings, dt: datetime | None = None) -> bool:
    """True selama window singkat di sekitar PRE_OPEN_CHECK_TIME (default 08:30 WIB),
    dipakai scheduler untuk memicu satu kali catch-up job sebelum market open."""
    dt = dt or now_wib()
    if not is_trading_day(dt):
        return False
    return dt.time() >= settings.pre_open_check_time and dt.time() < settings.market_open_time


def last_trading_day_str(dt: datetime | None = None) -> str:
    """Tanggal (YYYYMMDD) hari bursa sebelumnya, melompati weekend.

    Dipakai sebagai dateFrom untuk pre-open catch-up, supaya pengumuman yang
    terbit setelah market close hari bursa sebelumnya (termasuk yang terbit
    Jumat sore sebelum weekend) tetap tertangkap saat catch-up Senin pagi.
    """
    dt = dt or now_wib()
    prev = dt - timedelta(days=1)
    while prev.weekday() not in _TRADING_WEEKDAYS:
        prev -= timedelta(days=1)
    return prev.strftime("%Y%m%d")
