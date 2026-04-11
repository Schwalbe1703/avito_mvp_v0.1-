from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ads_models import Ad, Category
from app.ads_schemas import AdOut, CategoryOut
from app.admin_common import require_admin
from app.auth import get_current_user
from app.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


def api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )


class CategoryPriceIn(BaseModel):
    subscription_price: float = Field(..., ge=0)


class BlockAdIn(BaseModel):
    reason: str = Field(..., min_length=1)


@router.get("/ads/moderation", response_model=list[AdOut])
def moderation_queue(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)
    return (
        db.query(Ad)
        .filter(Ad.status == "moderation")
        .order_by(Ad.created_at.asc())
        .all()
    )


@router.post("/ads/{ad_id}/approve", response_model=AdOut)
def approve_ad(
    ad_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    ad.status = "approved"
    if hasattr(ad, "blocked_reason"):
        ad.blocked_reason = None
    if hasattr(ad, "blocked_at"):
        ad.blocked_at = None

    db.commit()
    db.refresh(ad)
    return ad


@router.post("/ads/{ad_id}/block", response_model=AdOut)
def block_ad(
    ad_id: UUID,
    payload: BlockAdIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)

    reason = payload.reason.strip()
    if not reason:
        raise api_error(422, "block_reason_required", "Нужно указать причину блокировки")

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise api_error(404, "ad_not_found", "Объявление не найдено")

    ad.status = "blocked"
    if hasattr(ad, "blocked_reason"):
        ad.blocked_reason = reason
    if hasattr(ad, "blocked_at"):
        ad.blocked_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ad)
    return ad


@router.post("/categories/{category_slug}/set_price", response_model=CategoryOut)
def set_category_price(
    category_slug: str,
    payload: CategoryPriceIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)

    category = db.query(Category).filter(Category.slug == category_slug).first()
    if not category:
        raise api_error(404, "category_not_found", "Категория не найдена")

    category.subscription_price = payload.subscription_price
    db.commit()
    db.refresh(category)
    return category