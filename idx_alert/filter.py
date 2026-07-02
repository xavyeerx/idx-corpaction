"""Pencocokan keyword terhadap subject pengumuman (PRD bagian 5)."""
from __future__ import annotations

from idx_alert.config import CategoryRule
from idx_alert.models import Announcement, MatchedAnnouncement


def match_category(announcement: Announcement, categories: list[CategoryRule]) -> MatchedAnnouncement | None:
    subject_lower = announcement.subject.lower()
    for category in categories:
        for keyword in category.keywords:
            if keyword.lower() in subject_lower:
                return MatchedAnnouncement(
                    announcement=announcement,
                    category_name=category.name,
                    category_label=category.label,
                    category_emoji=category.emoji,
                )
    return None
