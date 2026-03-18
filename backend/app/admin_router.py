from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.auth import get_current_user
from app.ads_models import Ad, Category
from app.ads_schemas import AdOut, CategoryOut
from app.admin_common import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])




class CategoryPriceIn(BaseModel):
    subscription_price: float = Field(..., ge=0)


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
    ad_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    ad.status = "approved"
    # clear block meta if present
    if hasattr(ad, "blocked_reason"):
        ad.blocked_reason = None
    if hasattr(ad, "blocked_at"):
        ad.blocked_at = None

    db.commit()
    db.refresh(ad)
    return ad


@router.post("/ads/{ad_id}/block", response_model=AdOut)
def block_ad(
    ad_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_admin(user)

    reason = payload.get("reason")
    if not reason or not str(reason).strip():
        raise HTTPException(status_code=422, detail="reason is required")

    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    ad.status = "blocked"
    if hasattr(ad, "blocked_reason"):
        ad.blocked_reason = str(reason).strip()
    if hasattr(ad, "blocked_at"):
        ad.blocked_at = None  # optional: set in DB via now if you want
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

    c = db.query(Category).filter(Category.slug == category_slug).first()
    if not c:
        raise HTTPException(status_code=404, detail="Category not found")

    c.subscription_price = payload.subscription_price
    db.commit()
    db.refresh(c)
    return c