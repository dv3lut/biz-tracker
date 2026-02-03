"""Helpers for region definitions and persistence."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.utils.regions import get_region_definitions


def list_regions(session: Session, *, create_if_missing: bool = True) -> list[models.Region]:
    stmt = select(models.Region).order_by(models.Region.order_index, models.Region.name)
    regions = list(session.execute(stmt).scalars())
    if not create_if_missing:
        return regions

    existing_by_code = {region.code: region for region in regions}
    created = False
    for definition in get_region_definitions():
        if definition.code in existing_by_code:
            continue
        region = models.Region(
            code=definition.code,
            name=definition.name,
            order_index=definition.order_index,
        )
        session.add(region)
        existing_by_code[definition.code] = region
        created = True

    if created:
        session.flush()
        regions = list(session.execute(stmt).scalars())

    return regions


__all__ = ["list_regions"]
