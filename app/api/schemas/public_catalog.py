"""Schemas publics pour le catalogue NAF."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class PublicNafCategoryOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    active_subcategory_count: int


__all__ = ["PublicNafCategoryOut"]
