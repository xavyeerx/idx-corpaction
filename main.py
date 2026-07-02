"""Entrypoint sistem alert otomatis keterbukaan informasi aksi korporasi IDX.

Alur (PRD bagian 4, 8, 9 + pre-open catch-up):
- Di luar jam bursa: proses tidur, hanya bangun sekali di sekitar PRE_OPEN_CHECK_TIME
  (default 08:30 WIB) untuk mengecek pengumuman yang terbit sejak market close
  terakhir, supaya ada alert sebelum bursa buka jam 08:45.
- Selama jam bursa: polling berkala sesuai POLL_INTERVAL_SECONDS, dengan exponential
  backoff saat error/rate limit, dan notifikasi admin kalau gagal berturut-turut
  melewati ambang batas.
"""
from __future__ import annotations

import time

from idx_alert.config import load_settings
from idx_alert.dedup import Deduplicator
from idx_alert.logger import setup_logger
from idx_alert.market_hours import is_market_open, is_pre_open_check_time, now_wib
from idx_alert.notifier import TelegramNotifier
from idx_alert.pipeline import run_once

_IDLE_SLEEP_SECONDS = 60  # cek status jam bursa tiap 1 menit saat idle di luar jam bursa
_PRE_OPEN_COOLDOWN_SECONDS = 3600  # jangan re-trigger pre-open check berkali-kali dalam window-nya


def main() -> None:
    settings = load_settings()
    logger = setup_logger(settings.log_file_path, settings.log_level)
    dedup = Deduplicator(settings.sqlite_db_path)
    notifier = TelegramNotifier(settings, logger)

    logger.info("Sistem alert IDX corporate action dimulai.")

    consecutive_failures = 0
    current_backoff = settings.poll_interval_seconds
    admin_warned = False
    last_pre_open_check_date = None

    while True:
        try:
            now = now_wib()

            if is_market_open(settings, now):
                sent = run_once(settings, dedup, notifier, logger)
                if sent:
                    logger.info("%d alert baru terkirim pada siklus ini.", sent)

                consecutive_failures = 0
                current_backoff = settings.poll_interval_seconds
                admin_warned = False
                time.sleep(current_backoff)
                continue

            if is_pre_open_check_time(settings, now) and last_pre_open_check_date != now.date():
                logger.info("Menjalankan pre-open catch-up check sebelum market open.")
                sent = run_once(settings, dedup, notifier, logger)
                logger.info("Pre-open catch-up selesai, %d alert terkirim.", sent)
                last_pre_open_check_date = now.date()
                time.sleep(_PRE_OPEN_COOLDOWN_SECONDS)
                continue

            time.sleep(_IDLE_SLEEP_SECONDS)

        except Exception as exc:  # noqa: BLE001 - loop utama tidak boleh mati karena satu error
            consecutive_failures += 1
            logger.error(
                "Error pada siklus polling (%d berturut-turut): %s", consecutive_failures, exc
            )

            if (
                consecutive_failures >= settings.poll_max_consecutive_failures
                and not admin_warned
            ):
                try:
                    notifier.send_admin_warning(
                        f"⚠️ Sistem monitoring IDX corporate action bermasalah: "
                        f"{consecutive_failures} kegagalan berturut-turut. Error terakhir: {exc}"
                    )
                    admin_warned = True
                except Exception as notify_exc:  # noqa: BLE001
                    logger.error("Gagal mengirim admin warning: %s", notify_exc)

            current_backoff = min(current_backoff * 2, settings.poll_backoff_max_seconds)
            time.sleep(current_backoff)


if __name__ == "__main__":
    main()
