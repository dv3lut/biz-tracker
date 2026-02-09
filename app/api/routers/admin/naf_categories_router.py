"""Admin endpoints to manage NAF categories, sub-categories and pricing."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db_session
from app.api.schemas import (
    DepartmentOut,
    NafCategoryCreate,
    NafCategoryOut,
    NafCategoryUpdate,
    NafCategorySubCategoryLink,
    NafSubCategoryCreate,
    NafSubCategoryOut,
    NafSubCategoryUpdate,
)
from app.db import models
from app.services.client_service import build_subcategory_department_index, get_active_clients
from app.utils.naf import ensure_valid_naf_code, euros_to_cents

router = APIRouter(tags=["admin"])


def _normalize_name(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Le champ {field} est obligatoire.",
        )
    return normalized


def _normalize_keywords(raw_keywords: list[str] | None) -> list[str]:
    if not raw_keywords:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for keyword in raw_keywords:
        if keyword is None:
            continue
        token = keyword.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(token)
    return normalized


def _get_category_or_404(session: Session, category_id: UUID) -> models.NafCategory:
    stmt = (
        select(models.NafCategory)
        .where(models.NafCategory.id == category_id)
        .options(selectinload(models.NafCategory.subcategories))
    )
    category = session.execute(stmt).scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable.")
    return category


def _get_subcategory_or_404(session: Session, subcategory_id: UUID) -> models.NafSubCategory:
    subcategory = session.get(models.NafSubCategory, subcategory_id)
    if subcategory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sous-catégorie introuvable.")
    return subcategory


def _get_category_link(
    session: Session,
    *,
    category_id: UUID,
    subcategory_id: UUID,
) -> models.NafCategorySubCategory | None:
    stmt = select(models.NafCategorySubCategory).where(
        models.NafCategorySubCategory.category_id == category_id,
        models.NafCategorySubCategory.subcategory_id == subcategory_id,
    )
    return session.execute(stmt).scalar_one_or_none()


@router.get("/naf-categories", response_model=list[NafCategoryOut], summary="Lister les catégories NAF")
def list_naf_categories(session: Session = Depends(get_db_session)) -> list[NafCategoryOut]:
    stmt = (
        select(models.NafCategory)
        .options(selectinload(models.NafCategory.subcategories))
        .order_by(models.NafCategory.name)
    )
    categories = session.execute(stmt).scalars().all()

    departments = session.execute(
        select(models.Department).order_by(models.Department.order_index)
    ).scalars().all()
    department_by_id = {department.id: department for department in departments}
    active_clients = get_active_clients(session)
    subcategory_departments, subcategory_all_departments = build_subcategory_department_index(active_clients)

    output: list[NafCategoryOut] = []
    for category in categories:
        subcategories: list[NafSubCategoryOut] = []
        for subcategory in category.subcategories:
            if subcategory.id in subcategory_all_departments:
                dept_count = len(departments)
                dept_all = True
                dept_items: list[models.Department] = []
            else:
                dept_ids = subcategory_departments.get(subcategory.id, set())
                dept_items = [department_by_id[dept_id] for dept_id in dept_ids if dept_id in department_by_id]
                dept_items.sort(key=lambda department: department.order_index)
                dept_count = len(dept_items)
                dept_all = False

            subcategory_out = NafSubCategoryOut.model_validate(subcategory).model_copy(
                update={
                    "google_department_count": dept_count,
                    "google_department_all": dept_all,
                    "google_departments": [
                        DepartmentOut.model_validate(department) for department in dept_items
                    ],
                }
            )
            subcategories.append(subcategory_out)

        category_out = NafCategoryOut.model_validate(category).model_copy(
            update={"subcategories": subcategories}
        )
        output.append(category_out)

    return output


@router.get("/naf-subcategories", response_model=list[NafSubCategoryOut], summary="Lister les sous-catégories NAF")
def list_naf_subcategories(session: Session = Depends(get_db_session)) -> list[NafSubCategoryOut]:
    stmt = select(models.NafSubCategory).order_by(models.NafSubCategory.name)
    subcategories = session.execute(stmt).scalars().all()

    departments = session.execute(
        select(models.Department).order_by(models.Department.order_index)
    ).scalars().all()
    department_by_id = {department.id: department for department in departments}
    active_clients = get_active_clients(session)
    subcategory_departments, subcategory_all_departments = build_subcategory_department_index(active_clients)

    output: list[NafSubCategoryOut] = []
    for subcategory in subcategories:
        if subcategory.id in subcategory_all_departments:
            dept_count = len(departments)
            dept_all = True
            dept_items: list[models.Department] = []
        else:
            dept_ids = subcategory_departments.get(subcategory.id, set())
            dept_items = [department_by_id[dept_id] for dept_id in dept_ids if dept_id in department_by_id]
            dept_items.sort(key=lambda department: department.order_index)
            dept_count = len(dept_items)
            dept_all = False

        subcategory_out = NafSubCategoryOut.model_validate(subcategory).model_copy(
            update={
                "google_department_count": dept_count,
                "google_department_all": dept_all,
                "google_departments": [
                    DepartmentOut.model_validate(department) for department in dept_items
                ],
            }
        )
        output.append(subcategory_out)

    return output


@router.post(
    "/naf-categories",
    response_model=NafCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une catégorie NAF",
)
def create_naf_category(payload: NafCategoryCreate, session: Session = Depends(get_db_session)) -> NafCategoryOut:
    name = _normalize_name(payload.name, field="nom")
    keywords = _normalize_keywords(payload.keywords)
    category = models.NafCategory(name=name, description=payload.description, keywords=keywords)
    session.add(category)

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une catégorie avec ce nom existe déjà.") from exc

    session.refresh(category)
    return NafCategoryOut.model_validate(category)


@router.put("/naf-categories/{category_id}", response_model=NafCategoryOut, summary="Mettre à jour une catégorie")
def update_naf_category(
    category_id: UUID,
    payload: NafCategoryUpdate,
    session: Session = Depends(get_db_session),
) -> NafCategoryOut:
    category = _get_category_or_404(session, category_id)
    if payload.name is not None:
        category.name = _normalize_name(payload.name, field="nom")
    if payload.description is not None:
        category.description = payload.description.strip() or None
    if payload.keywords is not None:
        category.keywords = _normalize_keywords(payload.keywords)

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une catégorie avec ce nom existe déjà.") from exc

    session.refresh(category)
    return NafCategoryOut.model_validate(category)


@router.delete("/naf-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une catégorie")
def delete_naf_category(category_id: UUID, session: Session = Depends(get_db_session)) -> None:
    category = _get_category_or_404(session, category_id)
    session.delete(category)
    session.flush()


@router.post(
    "/naf-subcategories",
    response_model=NafSubCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une sous-catégorie NAF",
)
def create_naf_subcategory(payload: NafSubCategoryCreate, session: Session = Depends(get_db_session)) -> NafSubCategoryOut:
    category = _get_category_or_404(session, payload.category_id)
    name = _normalize_name(payload.name, field="nom")
    try:
        naf_code = ensure_valid_naf_code(payload.naf_code)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    price_cents = euros_to_cents(payload.price_eur or 0)
    description = (payload.description.strip() or None) if payload.description is not None else None
    subcategory = models.NafSubCategory(
        name=name,
        description=description,
        naf_code=naf_code,
        price_cents=price_cents,
        is_active=payload.is_active,
    )
    session.add(subcategory)
    session.add(
        models.NafCategorySubCategory(
            category_id=category.id,
            subcategory=subcategory,
        )
    )

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une sous-catégorie avec ce code existe déjà.",
        ) from exc

    session.refresh(subcategory)
    return NafSubCategoryOut.model_validate(subcategory)


@router.put(
    "/naf-subcategories/{subcategory_id}",
    response_model=NafSubCategoryOut,
    summary="Mettre à jour une sous-catégorie",
)
def update_naf_subcategory(
    subcategory_id: UUID,
    payload: NafSubCategoryUpdate,
    session: Session = Depends(get_db_session),
) -> NafSubCategoryOut:
    subcategory = _get_subcategory_or_404(session, subcategory_id)
    if payload.name is not None:
        subcategory.name = _normalize_name(payload.name, field="nom")
    if payload.naf_code is not None:
        try:
            subcategory.naf_code = ensure_valid_naf_code(payload.naf_code)
        except ValueError as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    if payload.price_eur is not None:
        subcategory.price_cents = euros_to_cents(payload.price_eur)
    if payload.is_active is not None:
        subcategory.is_active = payload.is_active
    if payload.description is not None:
        subcategory.description = payload.description.strip() or None

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une sous-catégorie avec ce code existe déjà.",
        ) from exc

    session.refresh(subcategory)
    return NafSubCategoryOut.model_validate(subcategory)


@router.post(
    "/naf-categories/{category_id}/subcategories",
    response_model=NafSubCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Associer une sous-catégorie existante à une catégorie",
)
def attach_naf_subcategory(
    category_id: UUID,
    payload: NafCategorySubCategoryLink,
    session: Session = Depends(get_db_session),
) -> NafSubCategoryOut:
    _get_category_or_404(session, category_id)
    subcategory = _get_subcategory_or_404(session, payload.subcategory_id)
    existing = _get_category_link(
        session,
        category_id=category_id,
        subcategory_id=subcategory.id,
    )
    if existing is not None:
        return NafSubCategoryOut.model_validate(subcategory)
    session.add(
        models.NafCategorySubCategory(
            category_id=category_id,
            subcategory_id=subcategory.id,
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette sous-catégorie est déjà associée à la catégorie.",
        ) from exc
    session.refresh(subcategory)
    return NafSubCategoryOut.model_validate(subcategory)


@router.delete(
    "/naf-categories/{category_id}/subcategories/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer une sous-catégorie d'une catégorie",
)
def detach_naf_subcategory(
    category_id: UUID,
    subcategory_id: UUID,
    session: Session = Depends(get_db_session),
) -> None:
    _get_category_or_404(session, category_id)
    _get_subcategory_or_404(session, subcategory_id)
    link = _get_category_link(
        session,
        category_id=category_id,
        subcategory_id=subcategory_id,
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Association introuvable.")
    session.delete(link)
    session.flush()


@router.delete(
    "/naf-subcategories/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une sous-catégorie",
)
def delete_naf_subcategory(subcategory_id: UUID, session: Session = Depends(get_db_session)) -> None:
    subcategory = _get_subcategory_or_404(session, subcategory_id)
    session.delete(subcategory)
    session.flush()