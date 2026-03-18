"""ads boosting

Revision ID: 7c33f0160cba
Revises: 81a9263c4415
Create Date: 2026-03-11 11:53:44.940704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c33f0160cba'
down_revision: Union[str, None] = '81a9263c4415'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("ads", sa.Column("boosted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ads", sa.Column("last_free_boost_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_ads_boosted_at", "ads", ["boosted_at"])
    op.create_index("ix_ads_last_free_boost_at", "ads", ["last_free_boost_at"])


def downgrade() -> None:
    op.drop_index("ix_ads_last_free_boost_at", table_name="ads")
    op.drop_index("ix_ads_boosted_at", table_name="ads")
    op.drop_column("ads", "last_free_boost_at")
    op.drop_column("ads", "boosted_at")
