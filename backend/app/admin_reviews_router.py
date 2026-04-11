from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.admin_common import require_admin
from app.admin_schemas import (
    AdminReviewDetailOut,
    AdminReviewListItemOut,
    AdminReviewVisibilityOut,
)
from app.ads_models import Review, ReviewMessage
from app.ads_schemas import ReviewMessageOut
from app.auth import get_current_user
from app.deps import get_db
from app.reviews_common import recompute_ad_rating

router = APIRouter(prefix="/admin/reviews", tags=["admin-reviews"])


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


def get_review_or_404(db: Session, review_id: UUID) -> Review:
    review = (
        db.query(Review)
        .options(
            joinedload(Review.ad),
            joinedload(Review.messages),
        )
        .filter(Review.id == review_id)
        .first()
    )
    if not review:
        raise api_error(404, "review_not_found", "Отзыв не найден")
    return review


@router.get("", response_model=list[AdminReviewListItemOut])
def admin_reviews_list(
    ad_id: UUID | None = Query(default=None),
    master_id: UUID | None = Query(default=None),
    author_id: UUID | None = Query(default=None),
    is_published: bool | None = Query(default=None),
    has_master_reply: bool | None = Query(default=None),
    has_admin_reply: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)

    query = (
        db.query(Review)
        .options(
            joinedload(Review.ad),
            joinedload(Review.messages),
        )
    )

    if ad_id:
        query = query.filter(Review.ad_id == ad_id)

    if master_id:
        query = query.filter(Review.master_id == master_id)

    if author_id:
        query = query.filter(Review.author_id == author_id)

    if is_published is not None:
        query = query.filter(Review.is_published == is_published)

    if has_master_reply is True:
        query = query.filter(Review.messages.any(ReviewMessage.author_role == "master"))
    elif has_master_reply is False:
        query = query.filter(~Review.messages.any(ReviewMessage.author_role == "master"))

    if has_admin_reply is True:
        query = query.filter(Review.messages.any(ReviewMessage.author_role == "admin"))
    elif has_admin_reply is False:
        query = query.filter(~Review.messages.any(ReviewMessage.author_role == "admin"))

    reviews = (
        query.order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[AdminReviewListItemOut] = []

    for review in reviews:
        messages = list(review.messages or [])
        items.append(
            AdminReviewListItemOut(
                id=review.id,
                ad_id=review.ad_id,
                ad_title=getattr(review.ad, "title", "") if getattr(review, "ad", None) else "",
                master_id=review.master_id,
                author_id=review.author_id,
                rating=review.rating,
                text=review.text,
                is_published=review.is_published,
                created_at=review.created_at,
                updated_at=review.updated_at,
                messages_count=len(messages),
                has_master_reply=any(m.author_role == "master" for m in messages),
                has_admin_reply=any(m.author_role == "admin" for m in messages),
            )
        )

    return items


@router.get("/{review_id}", response_model=AdminReviewDetailOut)
def admin_review_detail(
    review_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    review = get_review_or_404(db, review_id)

    return AdminReviewDetailOut(
        id=review.id,
        ad_id=review.ad_id,
        ad_title=getattr(review.ad, "title", "") if getattr(review, "ad", None) else "",
        master_id=review.master_id,
        author_id=review.author_id,
        rating=review.rating,
        text=review.text,
        is_published=review.is_published,
        created_at=review.created_at,
        updated_at=review.updated_at,
        messages=[ReviewMessageOut.model_validate(m) for m in (review.messages or [])],
    )


@router.post("/{review_id}/hide", response_model=AdminReviewVisibilityOut)
def hide_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    review = get_review_or_404(db, review_id)

    if not review.is_published:
        return AdminReviewVisibilityOut(review_id=review.id, is_published=False)

    review.is_published = False
    db.flush()
    recompute_ad_rating(db, review.ad_id)
    db.commit()

    return AdminReviewVisibilityOut(review_id=review.id, is_published=False)


@router.post("/{review_id}/restore", response_model=AdminReviewVisibilityOut)
def restore_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_admin(user)
    review = get_review_or_404(db, review_id)

    if review.is_published:
        return AdminReviewVisibilityOut(review_id=review.id, is_published=True)

    review.is_published = True
    db.flush()
    recompute_ad_rating(db, review.ad_id)
    db.commit()

    return AdminReviewVisibilityOut(review_id=review.id, is_published=True)