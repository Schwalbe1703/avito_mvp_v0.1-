"""reviews

Revision ID: 81a9263c4415
Revises: 346552b4c268
Create Date: 2026-03-06 11:12:32.990114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql



# revision identifiers, used by Alembic.
revision: str = '81a9263c4415'
down_revision: Union[str, None] = '346552b4c268'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),

        sa.Column("ad_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),

        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),

        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),

        # for future moderation
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_check_constraint("ck_reviews_rating_1_5", "reviews", "rating >= 1 AND rating <= 5")
    op.create_unique_constraint("uq_reviews_ad_author", "reviews", ["ad_id", "author_id"])

    op.create_index("ix_reviews_ad_id", "reviews", ["ad_id"])
    op.create_index("ix_reviews_master_id", "reviews", ["master_id"])
    op.create_index("ix_reviews_created_at", "reviews", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reviews_created_at", table_name="reviews")
    op.drop_index("ix_reviews_master_id", table_name="reviews")
    op.drop_index("ix_reviews_ad_id", table_name="reviews")
    op.drop_constraint("uq_reviews_ad_author", "reviews", type_="unique")
    op.drop_constraint("ck_reviews_rating_1_5", "reviews", type_="check")
    op.drop_table("reviews")
