"""Struktur data internal untuk satu entri pengumuman IDX."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Announcement:
    emiten: str
    subject: str
    published_at: datetime  # waktu terbit resmi di sistem BEI (WIB)
    document_url: str
    source_id: str = ""  # Id2/NoPengumuman dari IDX, identitas resmi kalau tersedia

    @property
    def unique_id(self) -> str:
        """ID unik pengumuman (PRD bagian 6).

        Pakai source_id (Id2 dari IDX) kalau tersedia, karena itu identitas resmi
        satu pengumuman dan stabil antar-fetch. Fallback ke hash emiten+subject+
        document_url kalau source_id kosong (mis. sumber data lain di masa depan),
        meski document_url bisa tidak stabil kalau IDX mengubah urutan attachment.
        """
        if self.source_id:
            raw = f"{self.emiten}|{self.source_id}"
        else:
            raw = f"{self.emiten}|{self.subject}|{self.document_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchedAnnouncement:
    announcement: Announcement
    category_name: str
    category_label: str
    category_emoji: str
