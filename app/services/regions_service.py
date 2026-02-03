"""Helpers for region and department definitions and persistence."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.utils.regions import get_department_definitions, get_region_definitions


def list_regions(
    session: Session,
    *,
    create_if_missing: bool = True,
    include_departments: bool = False,
) -> list[models.Region]:
    stmt = select(models.Region).order_by(models.Region.order_index, models.Region.name)
    if include_departments:
        stmt = stmt.options(selectinload(models.Region.departments))
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


def list_departments(session: Session, *, create_if_missing: bool = True) -> list[models.Department]:
    stmt = select(models.Department).order_by(models.Department.order_index, models.Department.name)
    departments = list(session.execute(stmt).scalars())
    if not create_if_missing:
        return departments

    regions = list_regions(session)
    region_by_code = {region.code: region for region in regions}
    existing_by_code = {department.code: department for department in departments}
    created = False
    for definition in get_department_definitions():
        if definition.code in existing_by_code:
            continue
        region = region_by_code.get(definition.region_code)
        if region is None:
            continue
        department = models.Department(
            code=definition.code,
            name=definition.name,
            order_index=definition.order_index,
            region_id=region.id,
        )
        session.add(department)
        existing_by_code[definition.code] = department
        created = True

    if created:
        session.flush()
        departments = list(session.execute(stmt).scalars())

    return departments


__all__ = ["list_departments", "list_regions"]
