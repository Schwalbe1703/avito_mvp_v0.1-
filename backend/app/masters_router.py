from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.deps import get_db

from app.users_models import User
from app.cities_models import City
from app.ads_models import Ad, Category, Subscription

from app.ads_schemas import MyAdsStats, MySubscriptionsOut, SubscriptionOut
from app.masters_schemas import MasterDashboardOut, MasterMeOut

router = APIRouter(prefix="/masters", tags=["masters"])


def require_master(user):
    if getattr(user, "role", None) != "master":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def subscription_status(now: datetime, paid_until: datetime, grace_until: datetime) -> str:
    if grace_until >= now:
        return "active" if paid_until >= now else "grace"
    return "expired"


def get_city_by_id(db: Session, city_id):
    if not city_id:
        return None
    return db.query(City).filter(City.id == city_id, City.is_active == True).first()  # noqa: E712


@router.get("/me", response_model=MasterMeOut)
def me_master(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    u = db.query(User).filter(User.id == user.id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    city = get_city_by_id(db, getattr(u, "city_id", None))

    return MasterMeOut(
        id=u.id,
        name=u.name,
        phone=getattr(u, "phone", None),
        city_id=getattr(u, "city_id", None),
        city_slug=getattr(city, "slug", None) if city else None,
        city_title=getattr(city, "title", None) if city else None,
    )


@router.get("/me/dashboard", response_model=MasterDashboardOut)
def master_dashboard(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master(user)

    # profile
    u = db.query(User).filter(User.id == user.id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    city = get_city_by_id(db, getattr(u, "city_id", None))
    profile = MasterMeOut(
        id=u.id,
        name=u.name,
        phone=getattr(u, "phone", None),
        city_id=getattr(u, "city_id", None),
        city_slug=getattr(city, "slug", None) if city else None,
        city_title=getattr(city, "title", None) if city else None,
    )

    # ads stats
    rows = (
        db.query(Ad.status, Ad.archived_at, Ad.is_active)
        .filter(Ad.master_id == user.id)
        .all()
    )

    ads_stats = MyAdsStats()
    ads_stats.total = len(rows)

    for status, archived_at, is_active in rows:
        if status == "approved":
            ads_stats.approved += 1
        elif status == "moderation":
            ads_stats.moderation += 1
        elif status == "blocked":
            ads_stats.blocked += 1

        if archived_at is not None:
            ads_stats.archived += 1
        if is_active:
            ads_stats.active += 1

    # subscriptions
    now = datetime.now(timezone.utc)

    subs = (
        db.query(Subscription)
        .filter(Subscription.master_id == user.id)
        .all()
    )

    cat_ids = [s.category_id for s in subs]
    cats = {}
    if cat_ids:
        for c in db.query(Category).filter(Category.id.in_(cat_ids)).all():
            cats[c.id] = c

    items: list[SubscriptionOut] = []
    for s in subs:
        c = cats.get(s.category_id)
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
                status=subscription_status(now, s.paid_until, s.grace_until),
            )
        )

    subscriptions = MySubscriptionsOut(items=items)

    return MasterDashboardOut(profile=profile, ads_stats=ads_stats, subscriptions=subscriptions)