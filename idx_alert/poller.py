"""Poller untuk endpoint GetAnnouncement IDX (PRD bagian 3, 4, 8).

Endpoint dilindungi Cloudflare bot protection, sehingga wajib pakai cloudscraper
(bukan requests biasa) supaya lolos challenge dan dapat response JSON asli.

Karena endpoint hanya menerima satu keyword per request, satu siklus polling
terdiri dari N request berurutan, satu per kategori di config/keywords.yaml,
lalu hasilnya digabung sebelum diproses filter+dedup di pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime

import cloudscraper
import pytz
import requests

from idx_alert.config import Settings
from idx_alert.models import Announcement

WIB = pytz.timezone("Asia/Jakarta")

_ENDPOINT = "https://www.idx.co.id/primary/ListedCompany/GetAnnouncement"

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


class PollerError(Exception):
    pass


def _parse_published_at(raw: str) -> datetime:
    """TglPengumuman datang dalam format ISO 8601 tanpa timezone, sudah WIB."""
    naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
    return WIB.localize(naive)


def _primary_document_url(attachments: list[dict]) -> str:
    """Dokumen utama adalah attachment dengan IsAttachment=False; kalau tidak ada,
    pakai attachment pertama sebagai fallback."""
    for att in attachments:
        if not att.get("IsAttachment", True):
            return att.get("FullSavePath", "")
    if attachments:
        return attachments[0].get("FullSavePath", "")
    return ""


def _fetch_for_keyword(settings: Settings, keyword: str, date_from: str, date_to: str) -> list[dict]:
    params = {
        "kodeEmiten": "",
        "emitenType": "*",
        "indexFrom": 0,
        "pageSize": settings.poll_page_size,
        "dateFrom": date_from,
        "dateTo": date_to,
        "lang": "id",
        "keyword": keyword,
    }
    resp = _scraper.get(_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()

    try:
        payload = resp.json()
    except ValueError as exc:
        raise PollerError(f"Response bukan JSON valid untuk keyword {keyword!r}: {exc}") from exc

    return payload.get("Replies", [])


def fetch_announcements(
    settings: Settings, logger: logging.Logger, date_from: str | None = None
) -> list[Announcement]:
    """Jalankan satu siklus polling: satu request per kategori keyword, gabungkan hasil.

    Mengambil hanya keyword pertama tiap kategori sebagai representasi kategori itu,
    karena tujuan endpoint adalah menemukan entri yang match kategori, bukan expand
    ke seluruh sinonim di request terpisah (sinonim lain tetap dicek ulang saat
    pencocokan kategori di filter.py terhadap subject hasil).

    date_from (format YYYYMMDD) menentukan awal rentang pencarian; default hari ini.
    Dedup di pipeline yang mencegah re-alert, jadi rentang yang lebih lebar aman dipakai
    untuk menangkap pengumuman yang terbit saat sistem tidak jalan (mis. semalam/weekend).
    """
    date_to = datetime.now(WIB).strftime("%Y%m%d")
    date_from = date_from or date_to

    seen_ids: set[str] = set()
    announcements: list[Announcement] = []

    for category in settings.categories:
        keyword = category.keywords[0]
        try:
            replies = _fetch_for_keyword(settings, keyword, date_from, date_to)
        except (requests.RequestException, cloudscraper.exceptions.CloudflareException, PollerError) as exc:
            logger.error("Fetch gagal untuk kategori %s (keyword=%r): %s", category.name, keyword, exc)
            continue

        for reply in replies:
            pengumuman = reply.get("pengumuman", {})
            attachments = reply.get("attachments", [])

            emiten = str(pengumuman.get("Kode_Emiten", "")).strip()
            subject = str(pengumuman.get("JudulPengumuman", "")).strip()
            tgl_raw = pengumuman.get("TglPengumuman")

            if not emiten or not subject or not tgl_raw:
                logger.warning("Entri pengumuman tidak lengkap, dilewati: %s", pengumuman.get("Id2"))
                continue

            try:
                published_at = _parse_published_at(tgl_raw)
            except ValueError:
                logger.warning("Gagal parse TglPengumuman: %r, entri dilewati", tgl_raw)
                continue

            document_url = _primary_document_url(attachments)

            ann = Announcement(emiten, subject, published_at, document_url)
            if ann.unique_id in seen_ids:
                continue
            seen_ids.add(ann.unique_id)
            announcements.append(ann)

    return announcements
