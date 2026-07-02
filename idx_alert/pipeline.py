"""Pipeline inti: fetch -> filter -> dedup -> notify. Dipakai baik oleh polling loop
jam bursa maupun pre-open catch-up job."""
from __future__ import annotations

import logging

from idx_alert.config import Settings
from idx_alert.dedup import Deduplicator
from idx_alert.filter import match_category
from idx_alert.market_hours import now_wib
from idx_alert.notifier import TelegramNotifier
from idx_alert.poller import fetch_announcements


def run_once(
    settings: Settings,
    dedup: Deduplicator,
    notifier: TelegramNotifier,
    logger: logging.Logger,
) -> int:
    """Satu siklus fetch+proses. Return jumlah alert baru yang terkirim."""
    announcements = fetch_announcements(settings, logger)
    logger.debug("Fetch mengembalikan %d entri pengumuman", len(announcements))

    sent_count = 0
    for ann in announcements:
        match = match_category(ann, settings.categories)
        if match is None:
            continue

        ann_id = ann.unique_id
        if dedup.has_seen(ann_id):
            continue

        detected_at = now_wib()
        notifier.send_alert(match, detected_at)
        dedup.mark_seen(ann_id, ann.emiten, ann.subject)
        sent_count += 1

    return sent_count
