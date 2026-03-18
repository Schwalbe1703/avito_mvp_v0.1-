from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.ads_models import Subscription
from app.ads_schemas import MySubscriptionsOut, SubscriptionBuyIn, SubscriptionBuyOut, SubscriptionOut
from app.auth import get_current_user
from app.deps import get_db
from app.subscriptions_common import (
    extend_or_create_subscription,
    get_category_by_slug,
    sub_status,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def require_master(user):
    if getattr(user, "role", None) != "master":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@router.get("/my", response_model=MySubscriptionsOut)
def my_subscriptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)
    now = datetime.now(timezone.utc)

    subs = (
        db.query(Subscription)
        .options(joinedload(Subscription.category))
        .filter(Subscription.master_id == user.id)
        .order_by(Subscription.grace_until.desc(), Subscription.updated_at.desc())
        .all()
    )

    items: list[SubscriptionOut] = []
    for s in subs:
        c = s.category
        if not c:
            continue
        items.append(
            SubscriptionOut(
                id=s.id,
                category_id=c.id,
                category_slug=c.slug,
                category_title=c.title,
                price_per_day=float(getattr(c, "subscription_price", 0) or 0),
                paid_until=s.paid_until,
                grace_until=s.grace_until,
                status=sub_status(now, s.paid_until, s.grace_until),
            )
        )

    return MySubscriptionsOut(items=items)


@router.post("/buy", response_model=SubscriptionBuyOut)
def buy_subscription(
    payload: SubscriptionBuyIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)
    now = datetime.now(timezone.utc)

    category = get_category_by_slug(db, payload.category_slug)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    sub = extend_or_create_subscription(
        db,
        master_id=user.id,
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

    price = Decimal(str(getattr(category, "subscription_price", 0) or 0))
    amount = float(price * Decimal(payload.days))

    out = SubscriptionOut(
        id=sub.id,
        category_id=category.id,
        category_slug=category.slug,
        category_title=category.title,
        price_per_day=float(price),
        paid_until=sub.paid_until,
        grace_until=sub.grace_until,
        status=sub_status(now, sub.paid_until, sub.grace_until),
    )

    return SubscriptionBuyOut(subscription=out, amount=amount, currency="RUB")