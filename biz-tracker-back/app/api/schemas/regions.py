"""Schemas for French regions."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    order_index: int
    region_id: UUID


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    order_index: int
    departments: list[DepartmentOut] = Field(default_factory=list)


__all__ = ["DepartmentOut", "RegionOut"]
