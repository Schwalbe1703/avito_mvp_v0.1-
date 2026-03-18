"""ad photos

Revision ID: c7d9d0a90575
Revises: 5491336f0314
Create Date: 2026-03-04 12:02:42.831066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7d9d0a90575'
down_revision: Union[str, None] = '5491336f0314'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "ad_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ad_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ad_photos_ad_id", "ad_photos", ["ad_id"])
    op.create_index("ix_ad_photos_ad_sort", "ad_photos", ["ad_id", "sort_order"])
    op.create_unique_constraint("uq_ad_photos_storage_key", "ad_photos", ["storage_key"])


def downgrade() -> None:
    op.drop_constraint("uq_ad_photos_storage_key", "ad_photos", type_="unique")
    op.drop_index("ix_ad_photos_ad_sort", table_name="ad_photos")
    op.drop_index("ix_ad_photos_ad_id", table_name="ad_photos")
    op.drop_table("ad_photos")
