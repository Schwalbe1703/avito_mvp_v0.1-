import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    func,
    Boolean,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

# Association table: many-to-many ads <-> districts
ad_districts = sa.Table(
    "ad_districts",
    Base.metadata,
    sa.Column("ad_id", UUID(as_uuid=True), ForeignKey("ads.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("district_id", UUID(as_uuid=True), ForeignKey("districts.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    # floating price per day for subscription (admin can change)
    subscription_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ads: Mapped[list["Ad"]] = relationship(back_populates="category")  # noqa: F821
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="category")  # noqa: F821


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    city_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    price_from: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # legacy
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)

    work_time_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    show_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    price_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="moderation",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    boosted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_free_boost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    category: Mapped["Category"] = relationship(back_populates="ads")  # noqa: F821
    city_rel: Mapped[Optional["City"]] = relationship(back_populates="ads")  # noqa: F821

    districts_rel: Mapped[list["District"]] = relationship(  # noqa: F821
        "District",
        secondary=ad_districts,
        back_populates="ads_rel",
    )

    photos: Mapped[list["AdPhoto"]] = relationship(
        "AdPhoto",
        back_populates="ad",
        cascade="all, delete-orphan",
        order_by="AdPhoto.sort_order",
    )

    # NEW: reviews relationship
    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="ad",
        cascade="all, delete-orphan",
        order_by="Review.created_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("master_id", "category_id", name="uq_ads_master_category"),
        Index("ix_ads_category_status", "category_id", "status"),
    )

    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite",
        back_populates="ad",
        cascade="all, delete-orphan",
        order_by="Favorite.created_at.desc()",
    )


class AdPhoto(Base):
    __tablename__ = "ad_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    ad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ad: Mapped["Ad"] = relationship(back_populates="photos")  # noqa: F821


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    paid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category: Mapped["Category"] = relationship(back_populates="subscriptions")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("master_id", "category_id", name="uq_subscriptions_master_category"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    ad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # denormalized target (for future "reviews by master profile")
    master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # client author (nullable if user deleted)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    ad: Mapped["Ad"] = relationship("Ad", back_populates="reviews")  # noqa: F821

    messages: Mapped[list["ReviewMessage"]] = relationship(
        "ReviewMessage",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="ReviewMessage.created_at.asc()",
    )

    __table_args__ = (
        UniqueConstraint("ad_id", "author_id", name="uq_reviews_ad_author"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_1_5"),
        Index("ix_reviews_ad_id", "ad_id"),
        Index("ix_reviews_master_id", "master_id"),
        Index("ix_reviews_created_at", "created_at"),
    )
    
class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ad: Mapped["Ad"] = relationship("Ad", back_populates="favorites")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("client_id", "ad_id", name="uq_favorites_client_ad"),
        Index("ix_favorites_client_created_at", "client_id", "created_at"),
    )

class ReviewMessage(Base):
    __tablename__ = "review_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    author_role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # master|admin
    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    review: Mapped["Review"] = relationship("Review", back_populates="messages")  # noqa: F821

    __table_args__ = (
        CheckConstraint("author_role IN ('master', 'admin')", name="ck_review_messages_author_role"),
        Index("ix_review_messages_review_created_at", "review_id", "created_at"),
    )