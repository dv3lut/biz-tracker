"""Enumerations liées aux rejets day replay."""
from __future__ import annotations

from enum import Enum


class DayReplayReference(str, Enum):
    """Source de vérité utilisée pour rejouer une journée."""

    CREATION_DATE = "creation_date"
    INSERTION_DATE = "insertion_date"

    @property
    def label(self) -> str:
        if self is DayReplayReference.INSERTION_DATE:
            return "date d'insertion"
        return "date de création"


DEFAULT_DAY_REPLAY_REFERENCE = DayReplayReference.CREATION_DATE

__all__ = ["DayReplayReference", "DEFAULT_DAY_REPLAY_REFERENCE"]
