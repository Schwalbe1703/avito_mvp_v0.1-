from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminSubscriptionOut(BaseModel):
    id: UUID
    master_id: UUID

    category_id: UUID
    category_slug: str
    category_title: str

    price_per_day: float = 0.0

    paid_until: datetime
    grace_until: datetime
    status: str

    class Config:
        from_attributes = True


class AdminSubscriptionGrantIn(BaseModel):
    master_id: UUID
    category_slug: str = Field(..., min_length=1, max_length=50)
    days: int = Field(..., ge=1, le=3650)


class AdminSubscriptionRevokeIn(BaseModel):
    master_id: UUID
    category_slug: str = Field(..., min_length=1, max_length=50)