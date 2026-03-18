"""subscriptions

Revision ID: 346552b4c268
Revises: c7d9d0a90575
Create Date: 2026-03-04 15:20:31.575313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '346552b4c268'
down_revision: Union[str, None] = 'c7d9d0a90575'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) category price (per day, can be changed later by admin)
    op.add_column(
        "categories",
        sa.Column("subscription_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )

    # 2) subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_unique_constraint("uq_subscriptions_master_category", "subscriptions", ["master_id", "category_id"])
    op.create_index("ix_subscriptions_master_id", "subscriptions", ["master_id"])
    op.create_index("ix_subscriptions_category_id", "subscriptions", ["category_id"])
    op.create_index("ix_subscriptions_grace_until", "subscriptions", ["grace_until"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_grace_until", table_name="subscriptions")
    op.drop_index("ix_subscriptions_category_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_master_id", table_name="subscriptions")
    op.drop_constraint("uq_subscriptions_master_category", "subscriptions", type_="unique")
    op.drop_table("subscriptions")

    op.drop_column("categories", "subscription_price")
