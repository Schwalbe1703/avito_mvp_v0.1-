from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.ads_schemas import MyAdsStats, MySubscriptionsOut


class MasterMeOut(BaseModel):
    id: UUID
    name: str
    phone: Optional[str] = None

    city_id: Optional[UUID] = None
    city_slug: Optional[str] = None
    city_title: Optional[str] = None

    class Config:
        from_attributes = True


class MasterDashboardOut(BaseModel):
    profile: MasterMeOut
    ads_stats: MyAdsStats
    subscriptions: MySubscriptionsOut