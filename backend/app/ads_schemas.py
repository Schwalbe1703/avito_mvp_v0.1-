from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: UUID
    slug: str
    title: str
    subscription_price: float = 0.0  # price per day

    class Config:
        from_attributes = True


class CityOut(BaseModel):
    id: UUID
    slug: str
    title: str

    class Config:
        from_attributes = True


class DistrictOut(BaseModel):
    slug: str
    title: str

    class Config:
        from_attributes = True


class PhotoOut(BaseModel):
    id: UUID
    url: str
    sort_order: int = 0

    class Config:
        from_attributes = True


class AdCreate(BaseModel):
    category_slug: str = Field(..., min_length=1, max_length=50)
    city_slug: str = Field(..., min_length=1, max_length=50)

    district_slugs: list[str] = Field(default_factory=list)

    title: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1)
    price_from: Optional[int] = Field(default=None, ge=0)

    # legacy
    city: Optional[str] = Field(default=None, max_length=120)

    work_time_text: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=32)
    show_phone: bool = False
    price_note: Optional[str] = None


class AdUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    price_from: Optional[int] = Field(default=None, ge=0)

    city_slug: Optional[str] = Field(default=None, min_length=1, max_length=50)

    district_slugs: Optional[list[str]] = None

    # legacy
    city: Optional[str] = Field(default=None, max_length=120)

    work_time_text: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=32)
    show_phone: Optional[bool] = None
    price_note: Optional[str] = None
    is_active: Optional[bool] = None


class AdOut(BaseModel):
    id: UUID
    master_id: UUID
    category_id: UUID

    city_id: Optional[UUID] = None
    city_slug: Optional[str] = None
    city_title: Optional[str] = None

    districts: list[DistrictOut] = Field(default_factory=list)
    photos: list[PhotoOut] = Field(default_factory=list)
    cover_url: Optional[str] = None

    title: str
    description: str
    price_from: Optional[int] = None

    # legacy
    city: Optional[str] = None

    status: str

    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None

    work_time_text: Optional[str] = None
    price_note: Optional[str] = None
    is_active: bool = True
    archived_at: Optional[datetime] = None
    rating_avg: float = 0.0
    rating_count: int = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    boosted_at: Optional[datetime] = None
    last_free_boost_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdDetail(AdOut):
    contact_phone_masked: Optional[str] = None


class RevealPhoneResponse(BaseModel):
    phone: str


class AdOwnerDetail(AdOut):
    contact_phone: Optional[str] = None
    show_phone: bool = False


class MyAdsStats(BaseModel):
    total: int = 0
    approved: int = 0
    moderation: int = 0
    blocked: int = 0
    archived: int = 0
    active: int = 0


# ===== Master Cabinet =====
class CabinetActionFlags(BaseModel):
    can_edit: bool
    can_archive: bool
    can_unarchive: bool
    can_upload_photos: bool
    can_free_boost: bool
    free_boost_reason: Optional[str] = None


class CabinetSubscriptionOut(BaseModel):
    category_slug: str
    category_title: str
    subscription_price: float = 0.0

    has_subscription: bool
    paid_until: Optional[datetime] = None
    grace_until: Optional[datetime] = None

    is_paid_active: bool
    is_grace_active: bool
    is_visible_now: bool


class CabinetMasterSummary(BaseModel):
    user_id: UUID
    email: str
    role: str
    phone: Optional[str] = None


class CabinetAdItemOut(BaseModel):
    id: UUID
    title: str
    description: str
    status: str

    is_active: bool = True
    archived_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None

    created_at: Optional[datetime] = None
    boosted_at: Optional[datetime] = None
    last_free_boost_at: Optional[datetime] = None

    category_slug: str
    category_title: str

    city_slug: Optional[str] = None
    city_title: Optional[str] = None

    district_slugs: list[str] = Field(default_factory=list)
    district_titles: list[str] = Field(default_factory=list)

    cover_url: Optional[str] = None
    photos_count: int = 0

    subscription_visible_now: bool
    public_visible_now: bool

    actions: CabinetActionFlags


class MasterCabinetOut(BaseModel):
    master: CabinetMasterSummary
    stats: MyAdsStats

    subscriptions: list[CabinetSubscriptionOut] = Field(default_factory=list)

    total: int = 0
    limit: int = 20
    offset: int = 0

    ads: list[CabinetAdItemOut] = Field(default_factory=list)


# ===== Subscriptions =====
class SubscriptionBuyIn(BaseModel):
    category_slug: str = Field(..., min_length=1, max_length=50)
    days: int = Field(default=30, ge=1, le=365)


class SubscriptionOut(BaseModel):
    id: UUID
    category_id: UUID
    category_slug: str
    category_title: str
    price_per_day: float = 0.0

    paid_until: datetime
    grace_until: datetime

    status: str  # active|grace|expired

    class Config:
        from_attributes = True


class SubscriptionBuyOut(BaseModel):
    subscription: SubscriptionOut
    amount: float
    currency: str = "RUB"


class MySubscriptionsOut(BaseModel):
    items: list[SubscriptionOut] = Field(default_factory=list)


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: Optional[str] = Field(default=None, max_length=2000)


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    text: Optional[str] = Field(default=None, max_length=2000)


class ReviewOut(BaseModel):
    id: UUID
    rating: int
    text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReviewMessageCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class ReviewMessageUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=2000)


class ReviewMessageOut(BaseModel):
    id: UUID
    author_id: Optional[UUID] = None
    author_role: str
    text: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewThreadOut(BaseModel):
    review: ReviewOut
    messages: list[ReviewMessageOut] = Field(default_factory=list)