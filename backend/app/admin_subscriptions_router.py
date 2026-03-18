from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.admin_common import require_admin
from app.admin_subscriptions_schemas import (
    AdminSubscriptionGrantIn,
    AdminSubscriptionOut,
    AdminSubscriptionRevokeIn,
)
from app.ads_models import Category, Subscription
from app.auth import get_current_user
from app.deps import get_db
from app.subscriptions_common import (
    extend_or_create_subscription,
    get_category_by_slug,
    get_master_or_404,
    revoke_subscription_now,
    sub_status,
)

router = APIRouter(prefix="/admin/subscriptions", tags=["admin-subscriptions"])


def to_admin_subscription_out(sub: Subscription, now: datetime) -> AdminSubscriptionOut:
    category = sub.category
    return AdminSubscriptionOut(
        id=sub.id,
        master_id=sub.master_id,
        category_id=category.id,
        category_slug=category.slug,
        category_title=category.title,
        price_per_day=float(getattr(category, "subscription_price", 0) or 0),
        paid_until=sub.paid_until,
        grace_until=sub.grace_until,
        status=sub_status(now, sub.paid_until, sub.grace_until),
    )


@router.get("", response_model=list[AdminSubscriptionOut])
def admin_subscriptions_list(
    master_id: str | None = Query(default=None),
    category_slug: str | None = Query(default=None),
    status: str | None = Query(default=None, description="active|grace|expired"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    now = datetime.now(timezone.utc)

    q = (
        db.query(Subscription)
        .options(joinedload(Subscription.category))
    )

    if master_id:
        q = q.filter(Subscription.master_id == master_id)

    if category_slug:
        q = q.join(Subscription.category).filter(Category.slug == category_slug)

    if status is not None:
        if status == "active":
            q = q.filter(Subscription.paid_until >= now)
        elif status == "grace":
            q = q.filter(Subscription.paid_until < now, Subscription.grace_until >= now)
        elif status == "expired":
            q = q.filter(Subscription.grace_until < now)
        else:
            raise HTTPException(status_code=422, detail="Invalid status. Allowed: active, grace, expired")

    subs = (
        q.order_by(
            Subscription.grace_until.desc(),
            Subscription.updated_at.desc(),
            Subscription.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [to_admin_subscription_out(sub, now) for sub in subs]


@router.post("/grant", response_model=AdminSubscriptionOut)
def grant_subscription(
    payload: AdminSubscriptionGrantIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    now = datetime.now(timezone.utc)

    get_master_or_404(db, str(payload.master_id))

    category = get_category_by_slug(db, payload.category_slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    sub = extend_or_create_subscription(
        db,
        master_id=payload.master_id,
        category=category,
        days=payload.days,
        now=now,
    )

    db.commit()
    db.refresh(sub)

    sub = (
        db.query(Subscription)
        .options(joinedload(Subscription.category))
        .filter(Subscription.id == sub.id)
        .first()
    )

    return to_admin_subscription_out(sub, now)


@router.post("/revoke", response_model=AdminSubscriptionOut)
def revoke_subscription(
    payload: AdminSubscriptionRevokeIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    now = datetime.now(timezone.utc)

    get_master_or_404(db, str(payload.master_id))

    category = get_category_by_slug(db, payload.category_slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    sub = (
        db.query(Subscription)
        .options(joinedload(Subscription.category))
        .filter(
            Subscription.master_id == payload.master_id,
            Subscription.category_id == category.id,
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    revoke_subscription_now(sub, now=now)
    db.commit()
    db.refresh(sub)

    return to_admin_subscription_out(sub, now)