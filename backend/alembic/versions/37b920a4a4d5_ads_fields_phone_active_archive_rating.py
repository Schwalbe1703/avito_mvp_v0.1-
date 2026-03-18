"""ads fields: phone, active, archive, rating

Revision ID: 37b920a4a4d5
Revises: 82692be7ba69
Create Date: 2026-02-27 17:24:33.376424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37b920a4a4d5'
down_revision: Union[str, None] = '82692be7ba69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("work_time_text", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("contact_phone", sa.String(length=32), nullable=True))
    op.add_column("ads", sa.Column("show_phone", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("ads", sa.Column("price_note", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("ads", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ads", sa.Column("rating_avg", sa.Numeric(3, 2), server_default=sa.text("0"), nullable=False))
    op.add_column("ads", sa.Column("rating_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    op.create_index("ix_ads_is_active", "ads", ["is_active"])
    op.create_index("ix_ads_archived_at", "ads", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_ads_archived_at", table_name="ads")
    op.drop_index("ix_ads_is_active", table_name="ads")

    op.drop_column("ads", "rating_count")
    op.drop_column("ads", "rating_avg")
    op.drop_column("ads", "archived_at")
    op.drop_column("ads", "is_active")
    op.drop_column("ads", "price_note")
    op.drop_column("ads", "show_phone")
    op.drop_column("ads", "contact_phone")
    op.drop_column("ads", "work_time_text")
