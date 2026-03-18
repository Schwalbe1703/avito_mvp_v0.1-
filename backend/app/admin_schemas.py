from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.ads_schemas import ReviewMessageOut


class AdminReviewListItemOut(BaseModel):
    id: UUID
    ad_id: UUID
    ad_title: str
    master_id: UUID
    author_id: Optional[UUID] = None

    rating: int
    text: Optional[str] = None
    is_published: bool

    created_at: datetime
    updated_at: datetime

    messages_count: int = 0
    has_master_reply: bool = False
    has_admin_reply: bool = False


class AdminReviewDetailOut(BaseModel):
    id: UUID
    ad_id: UUID
    ad_title: str
    master_id: UUID
    author_id: Optional[UUID] = None

    rating: int
    text: Optional[str] = None
    is_published: bool

    created_at: datetime
    updated_at: datetime

    messages: list[ReviewMessageOut] = Field(default_factory=list)


class AdminReviewVisibilityOut(BaseModel):
    review_id: UUID
    is_published: bool