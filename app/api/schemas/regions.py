"""Schemas for French regions."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    order_index: int


__all__ = ["RegionOut"]
