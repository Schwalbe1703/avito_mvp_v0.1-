from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

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
    get_master_or_404,
    revoke_subscription_now,
    sub_status,
)

router = APIRouter(prefix="/admin/subscriptions", tags=["admin-subscriptions"])


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


def get_master_or_api_error(db: Session, master_id: UUID):
    try:
        return get_master_or_404(db, str(master_id))
    except HTTPException as exc:
        if exc.status_code in {403, 404}:
            raise api_error(404, "master_not_found", "Мастер не найден")
        raise


def get_category_or_404(db: Session, category_slug: str) -> Category:
    category = db.query(Category).filter(Category.slug == category_slug).first()
    if not category:
        raise api_error(404, "category_not_found", "Категория не найдена")
    return category


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
    master_id: UUID | None = Query(default=None),
    category_slug: str | None = Query(default=None),
    status: str | None = Query(default=None, description="active|grace|expired"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    now = datetime.now(timezone.utc)

    query = db.query(Subscription).options(joinedload(Subscription.category))

    if master_id:
        query = query.filter(Subscription.master_id == master_id)

    if category_slug:
        query = query.join(Subscription.category).filter(Category.slug == category_slug)

    if status is not None:
        if status == "active":
            query = query.filter(Subscription.paid_until >= now)
        elif status == "grace":
            query = query.filter(Subscription.paid_until < now, Subscription.grace_until >= now)
        elif status == "expired":
            query = query.filter(Subscription.grace_until < now)
        else:
            raise api_error(
                422,
                "invalid_subscription_status_filter",
                "Недопустимый статус фильтра",
                {"allowed": ["active", "grace", "expired"]},
            )

    subs = (
        query.order_by(
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

    get_master_or_api_error(db, payload.master_id)
    category = get_category_or_404(db, payload.category_slug)

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

    get_master_or_api_error(db, payload.master_id)
    category = get_category_or_404(db, payload.category_slug)

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
        raise api_error(404, "subscription_not_found", "Подписка не найдена")

    revoke_subscription_now(sub, now=now)
    db.commit()
    db.refresh(sub)

    return to_admin_subscription_out(sub, now)