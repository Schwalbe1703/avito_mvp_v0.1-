from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.ads_models import Ad, Review, ReviewMessage, Subscription
from app.ads_schemas import (
    ReviewCreate,
    ReviewMessageCreate,
    ReviewMessageOut,
    ReviewMessageUpdate,
    ReviewOut,
    ReviewThreadOut,
    ReviewUpdate,
)
from app.auth import get_current_user
from app.deps import get_db
from app.reviews_common import recompute_ad_rating


router = APIRouter(prefix="/ads", tags=["reviews"])


def require_client(user):
    if getattr(user, "role", None) != "client":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_master_or_admin(user):
    if getattr(user, "role", None) not in {"master", "admin"}:
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


def get_public_review_or_404(db: Session, ad_id: str, review_id: str) -> Review:
    get_public_ad_or_404(db, ad_id)

    review = (
        db.query(Review)
        .options(joinedload(Review.messages))
        .filter(
            Review.id == review_id,
            Review.ad_id == ad_id,
            Review.is_published == True,  # noqa: E712
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


def get_author_review_or_404(db: Session, ad_id: str, review_id: str, author_id) -> Review:
    review = (
        db.query(Review)
        .filter(
            Review.id == review_id,
            Review.ad_id == ad_id,
            Review.author_id == author_id,
            Review.is_published == True,  # noqa: E712
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


def get_review_for_reply_or_404(db: Session, ad_id: str, review_id: str, user) -> Review:
    review = (
        db.query(Review)
        .join(Review.ad)
        .filter(
            Review.id == review_id,
            Review.ad_id == ad_id,
            Review.is_published == True,  # noqa: E712
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if user.role == "master" and review.ad.master_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return review


def get_own_review_message_or_404(db: Session, review_id: str, message_id: str, user) -> ReviewMessage:
    message = (
        db.query(ReviewMessage)
        .filter(
            ReviewMessage.id == message_id,
            ReviewMessage.review_id == review_id,
            ReviewMessage.author_id == user.id,
            ReviewMessage.author_role == user.role,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


def normalize_review_text(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text or None


def normalize_message_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    return text


@router.get("/{ad_id}/reviews", response_model=list[ReviewOut])
def list_reviews(
    ad_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    get_public_ad_or_404(db, ad_id)

    reviews = (
        db.query(Review)
        .filter(
            Review.ad_id == ad_id,
            Review.is_published == True,  # noqa: E712
        )
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return reviews


@router.get("/{ad_id}/reviews/{review_id}/thread", response_model=ReviewThreadOut)
def get_review_thread(
    ad_id: str,
    review_id: str,
    db: Session = Depends(get_db),
):
    review = get_public_review_or_404(db, ad_id, review_id)
    return ReviewThreadOut(
        review=ReviewOut.model_validate(review),
        messages=[ReviewMessageOut.model_validate(m) for m in (review.messages or [])],
    )


@router.post("/{ad_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    ad_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)
    ad = get_public_ad_or_404(db, ad_id)

    if ad.master_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot review your own ad")

    review = Review(
        ad_id=ad.id,
        master_id=ad.master_id,
        author_id=user.id,
        rating=payload.rating,
        text=normalize_review_text(payload.text),
        is_published=True,
    )
    db.add(review)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You already left a review for this ad")

    recompute_ad_rating(db, ad.id)
    db.commit()
    db.refresh(review)

    return review


@router.patch("/{ad_id}/reviews/{review_id}", response_model=ReviewOut)
def update_review(
    ad_id: str,
    review_id: str,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)

    review = get_author_review_or_404(db, ad_id, review_id, user.id)

    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update")

    if "rating" in patch:
        review.rating = patch["rating"]

    if "text" in patch:
        review.text = normalize_review_text(patch["text"])

    db.flush()
    recompute_ad_rating(db, review.ad_id)
    db.commit()
    db.refresh(review)

    return review


@router.delete("/{ad_id}/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    ad_id: str,
    review_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_client(user)

    review = get_author_review_or_404(db, ad_id, review_id, user.id)
    target_ad_id = review.ad_id

    db.delete(review)
    db.flush()
    recompute_ad_rating(db, target_ad_id)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{ad_id}/reviews/{review_id}/messages",
    response_model=ReviewMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_review_message(
    ad_id: str,
    review_id: str,
    payload: ReviewMessageCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master_or_admin(user)
    review = get_review_for_reply_or_404(db, ad_id, review_id, user)

    message = ReviewMessage(
        review_id=review.id,
        author_id=user.id,
        author_role=user.role,
        text=normalize_message_text(payload.text),
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@router.patch(
    "/{ad_id}/reviews/{review_id}/messages/{message_id}",
    response_model=ReviewMessageOut,
)
def update_review_message(
    ad_id: str,
    review_id: str,
    message_id: str,
    payload: ReviewMessageUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master_or_admin(user)
    get_review_for_reply_or_404(db, ad_id, review_id, user)

    message = get_own_review_message_or_404(db, review_id, message_id, user)

    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update")

    if "text" in patch:
        message.text = normalize_message_text(patch["text"])

    db.commit()
    db.refresh(message)

    return message


@router.delete(
    "/{ad_id}/reviews/{review_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_review_message(
    ad_id: str,
    review_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user = require_master_or_admin(user)
    get_review_for_reply_or_404(db, ad_id, review_id, user)

    message = get_own_review_message_or_404(db, review_id, message_id, user)

    db.delete(message)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)