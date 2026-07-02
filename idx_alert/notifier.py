"""Pengiriman alert ke Telegram Bot API dengan retry/backoff (PRD bagian 7, 9)."""
from __future__ import annotations

import logging
import time
from datetime import datetime

import requests

from idx_alert.config import Settings
from idx_alert.models import MatchedAnnouncement

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_RETRIES = 5
_INITIAL_BACKOFF_SECONDS = 2


def format_alert_message(match: MatchedAnnouncement, detected_at: datetime) -> str:
    ann = match.announcement
    delay_seconds = max(0, int((detected_at - ann.published_at).total_seconds()))

    published_str = ann.published_at.strftime("%d %b %Y, %H:%M WIB")
    detected_str = detected_at.strftime("%H:%M:%S WIB")

    doc_line = f"\U0001F4C4 Dokumen: {ann.document_url}" if ann.document_url else "\U0001F4C4 Dokumen: (tidak tersedia)"

    return (
        f"{match.category_emoji} {match.category_label} — {ann.emiten}\n\n"
        f"Subject: {ann.subject}\n\n"
        f"Terbit di IDX: {published_str}\n"
        f"Terdeteksi bot: {detected_str} (delay ~{delay_seconds} detik)\n\n"
        f"{doc_line}\n\n"
        f"Bukan rekomendasi beli/jual. DYOR."
    )


class TelegramNotifier:
    def __init__(self, settings: Settings, logger: logging.Logger):
        self._settings = settings
        self._logger = logger

    def _send(self, chat_id: str, text: str) -> None:
        url = _TELEGRAM_API.format(token=self._settings.telegram_bot_token)
        backoff = _INITIAL_BACKOFF_SECONDS

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return
                if resp.status_code == 429:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", backoff)
                    self._logger.warning("Telegram rate limited, retry_after=%s", retry_after)
                    time.sleep(retry_after)
                    continue
                self._logger.error("Telegram API error %s: %s", resp.status_code, resp.text)
            except requests.RequestException as exc:
                self._logger.error("Gagal kirim ke Telegram (percobaan %d/%d): %s", attempt, _MAX_RETRIES, exc)

            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

        raise RuntimeError(f"Gagal mengirim pesan Telegram setelah {_MAX_RETRIES} percobaan")

    def send_alert(self, match: MatchedAnnouncement, detected_at: datetime) -> None:
        text = format_alert_message(match, detected_at)
        self._send(self._settings.telegram_chat_id, text)
        self._logger.info(
            "Alert terkirim: [%s] %s - %s", match.category_name, match.announcement.emiten, match.announcement.subject
        )

    def send_admin_warning(self, text: str) -> None:
        self._send(self._settings.telegram_admin_chat_id, text)
