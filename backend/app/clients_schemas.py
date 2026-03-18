from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FavoriteToggleOut(BaseModel):
    is_favorite: bool


class ClientFavoriteItemOut(BaseModel):
    favorited_at: datetime

    ad_id: UUID
    title: str
    price_from: Optional[int] = None
    cover_url: Optional[str] = None

    category_slug: str
    category_title: str

    city_slug: Optional[str] = None
    city_title: Optional[str] = None

    rating_avg: float = 0.0
    rating_count: int = 0


class ClientReviewItemOut(BaseModel):
    review_id: UUID

    ad_id: UUID
    ad_title: str
    cover_url: Optional[str] = None

    rating: int
    text: Optional[str] = None

    created_at: datetime
    updated_at: datetime