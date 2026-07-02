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

    @property
    def unique_id(self) -> str:
        """ID unik dari kombinasi kode emiten + subject + link dokumen (PRD bagian 6)."""
        raw = f"{self.emiten}|{self.subject}|{self.document_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchedAnnouncement:
    announcement: Announcement
    category_name: str
    category_label: str
    category_emoji: str
