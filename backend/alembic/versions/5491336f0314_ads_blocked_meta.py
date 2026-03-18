"""ads blocked meta

Revision ID: 5491336f0314
Revises: be2c20438ef0
Create Date: 2026-03-04 10:46:12.736506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5491336f0314'
down_revision: Union[str, None] = 'be2c20438ef0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("ads", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.add_column("ads", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ads_blocked_at", "ads", ["blocked_at"])


def downgrade() -> None:
    op.drop_index("ix_ads_blocked_at", table_name="ads")
    op.drop_column("ads", "blocked_at")
    op.drop_column("ads", "blocked_reason")
