from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.ads_models import Ad, Favorite, Review, Subscription
from app.auth import get_current_user
from app.clients_schemas import (
    ClientFavoriteItemOut,
    ClientReviewItemOut,
    FavoriteToggleOut,
)
from app.deps import get_db

router = APIRouter(prefix="/clients", tags=["clients"])


def require_client(user):
    if getattr(user, "role", None) != "client":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def public_ad_query(db: Session):
    return (
        db.query(Ad)
        .join(
            Subscription,
            (Subscription.master_id == Ad.master_id) & (Subscription.category_id == Ad.category_id),
        )
        .filter(
            Ad.status == "approved",
            Ad.is_active == True,  # noqa: E712
            Ad.archived_at.is_(None),
            Subscription.grace_until >= func.now(),
        )
    )


def get_public_ad_or_404(db: Session, ad_id: str) -> Ad:
    ad = public_ad_query(db).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return ad


@router.post("/ads/{ad_id}/favorite", response_model=FavoriteToggleOut)
def add_to_favorites(
    ad_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)
    ad = get_public_ad_or_404(db, ad_id)

    existing = (
        db.query(Favorite)
        .filter(Favorite.client_id == user.id, Favorite.ad_id == ad.id)
        .first()
    )
    if existing:
        return FavoriteToggleOut(is_favorite=True)

    fav = Favorite(client_id=user.id, ad_id=ad.id)
    db.add(fav)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    return FavoriteToggleOut(is_favorite=True)


@router.delete("/ads/{ad_id}/favorite", response_model=FavoriteToggleOut)
def remove_from_favorites(
    ad_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)

    fav = (
        db.query(Favorite)
        .filter(Favorite.client_id == user.id, Favorite.ad_id == ad_id)
        .first()
    )
    if fav:
        db.delete(fav)
        db.commit()

    return FavoriteToggleOut(is_favorite=False)


@router.get("/me/favorites", response_model=list[ClientFavoriteItemOut])
def my_favorites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)

    favorites = (
        db.query(Favorite)
        .join(Favorite.ad)
        .join(
            Subscription,
            (Subscription.master_id == Ad.master_id) & (Subscription.category_id == Ad.category_id),
        )
        .filter(
            Favorite.client_id == user.id,
            Ad.status == "approved",
            Ad.is_active == True,  # noqa: E712
            Ad.archived_at.is_(None),
            Subscription.grace_until >= func.now(),
        )
        .options(
            joinedload(Favorite.ad).joinedload(Ad.category),
            joinedload(Favorite.ad).joinedload(Ad.city_rel),
            joinedload(Favorite.ad).joinedload(Ad.photos),
        )
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[ClientFavoriteItemOut] = []

    for fav in favorites:
        ad = fav.ad
        photos = list(getattr(ad, "photos", []) or [])
        cover_url = photos[0].url if photos else None

        items.append(
            ClientFavoriteItemOut(
                favorited_at=fav.created_at,
                ad_id=ad.id,
                title=ad.title,
                price_from=ad.price_from,
                cover_url=cover_url,
                category_slug=getattr(ad.category, "slug", ""),
                category_title=getattr(ad.category, "title", ""),
                city_slug=getattr(ad.city_rel, "slug", None) if getattr(ad, "city_rel", None) else None,
                city_title=getattr(ad.city_rel, "title", None) if getattr(ad, "city_rel", None) else None,
                rating_avg=float(ad.rating_avg or 0),
                rating_count=int(ad.rating_count or 0),
            )
        )

    return items


@router.get("/me/reviews", response_model=list[ClientReviewItemOut])
def my_reviews(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)

    reviews = (
        db.query(Review)
        .join(Review.ad)
        .filter(
            Review.author_id == user.id,
            Review.is_published == True,  # noqa: E712
        )
        .options(
            joinedload(Review.ad).joinedload(Ad.photos),
        )
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[ClientReviewItemOut] = []

    for review in reviews:
        ad = review.ad
        photos = list(getattr(ad, "photos", []) or []) if ad else []
        cover_url = photos[0].url if photos else None

        items.append(
            ClientReviewItemOut(
                review_id=review.id,
                ad_id=ad.id,
                ad_title=ad.title,
                cover_url=cover_url,
                rating=review.rating,
                text=review.text,
                created_at=review.created_at,
                updated_at=review.updated_at,
            )
        )

    return items