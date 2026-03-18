import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String, DateTime, Boolean, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(back_populates="city")  # noqa: F821
    ads: Mapped[list["Ad"]] = relationship(back_populates="city_rel")  # noqa: F821

    # NEW: districts in this city
    districts_rel: Mapped[list["District"]] = relationship(
        "District",
        back_populates="city_rel",
        cascade="all, delete-orphan",
    )


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    city_rel: Mapped["City"] = relationship("City", back_populates="districts_rel")

    # NEW: many-to-many with ads (secondary table lives in ads_models.py)
    ads_rel: Mapped[list["Ad"]] = relationship(  # noqa: F821
        "Ad",
        secondary="ad_districts",
        back_populates="districts_rel",
    )

    __table_args__ = (
        sa.UniqueConstraint("city_id", "slug", name="uq_districts_city_slug"),
    )