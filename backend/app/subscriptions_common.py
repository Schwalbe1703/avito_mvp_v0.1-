from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ads_models import Category, Subscription
from app.users_models import User

GRACE_HOURS = 24


def get_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.query(Category).filter(Category.slug == slug).first()


def get_master_or_404(db: Session, master_id: str) -> User:
    user = db.query(User).filter(User.id == master_id).first()
    if not user or getattr(user, "role", None) != "master":
        raise HTTPException(status_code=404, detail="Master not found")
    return user


def sub_status(now: datetime, paid_until: datetime, grace_until: datetime) -> str:
    if grace_until >= now:
        return "active" if paid_until >= now else "grace"
    return "expired"


def extend_or_create_subscription(
    db: Session,
    *,
    master_id,
    category: Category,
    days: int,
    now: datetime | None = None,
) -> Subscription:
    now = now or datetime.now(timezone.utc)

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.master_id == master_id,
            Subscription.category_id == category.id,
        )
        .first()
    )

    start_from = now
    if sub and sub.paid_until and sub.paid_until > now:
        start_from = sub.paid_until

    paid_until = start_from + timedelta(days=days)
    grace_until = paid_until + timedelta(hours=GRACE_HOURS)

    if not sub:
        sub = Subscription(
            master_id=master_id,
            category_id=category.id,
            paid_until=paid_until,
            grace_until=grace_until,
        )
        db.add(sub)
    else:
        sub.paid_until = paid_until
        sub.grace_until = grace_until

    return sub


def revoke_subscription_now(sub: Subscription, now: datetime | None = None) -> Subscription:
    now = now or datetime.now(timezone.utc)
    expired_at = now - timedelta(seconds=1)

    sub.paid_until = expired_at
    sub.grace_until = expired_at
    return sub