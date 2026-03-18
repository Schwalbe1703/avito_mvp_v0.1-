"""districts and ad_districts

Revision ID: be2c20438ef0
Revises: f0ed9ec684df
Create Date: 2026-03-02 13:30:02.843496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be2c20438ef0'
down_revision: Union[str, None] = 'f0ed9ec684df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "districts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("city_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_districts_city_slug", "districts", ["city_id", "slug"])
    op.create_index("ix_districts_city_id", "districts", ["city_id"])

    op.create_table(
        "ad_districts",
        sa.Column("ad_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("district_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("ad_id", "district_id", name="pk_ad_districts"),
    )
    op.create_index("ix_ad_districts_ad_id", "ad_districts", ["ad_id"])
    op.create_index("ix_ad_districts_district_id", "ad_districts", ["district_id"])


def downgrade() -> None:
    # ad_districts
    op.drop_index("ix_ad_districts_district_id", table_name="ad_districts")
    op.drop_index("ix_ad_districts_ad_id", table_name="ad_districts")
    op.drop_table("ad_districts")

    # districts
    op.drop_index("ix_districts_city_id", table_name="districts")
    op.drop_constraint("uq_districts_city_slug", "districts", type_="unique")
    op.drop_table("districts")