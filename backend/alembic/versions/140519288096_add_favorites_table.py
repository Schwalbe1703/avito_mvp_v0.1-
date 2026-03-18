"""add favorites table

Revision ID: 140519288096
Revises: 7c33f0160cba
Create Date: 2026-03-16 13:52:56.849765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "140519288096"
down_revision: Union[str, None] = "7c33f0160cba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("ad_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "ad_id", name="uq_favorites_client_ad"),
    )
    op.create_index(op.f("ix_favorites_ad_id"), "favorites", ["ad_id"], unique=False)
    op.create_index("ix_favorites_client_created_at", "favorites", ["client_id", "created_at"], unique=False)
    op.create_index(op.f("ix_favorites_client_id"), "favorites", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_favorites_client_id"), table_name="favorites")
    op.drop_index("ix_favorites_client_created_at", table_name="favorites")
    op.drop_index(op.f("ix_favorites_ad_id"), table_name="favorites")
    op.drop_table("favorites")