"""add review messages

Revision ID: 965c0257cc63
Revises: 140519288096
Create Date: 2026-03-17 07:14:14.164331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "965c0257cc63"
down_revision: Union[str, None] = "140519288096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("author_role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "author_role IN ('master', 'admin')",
            name="ck_review_messages_author_role",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_messages_author_id"), "review_messages", ["author_id"], unique=False)
    op.create_index(op.f("ix_review_messages_author_role"), "review_messages", ["author_role"], unique=False)
    op.create_index("ix_review_messages_review_created_at", "review_messages", ["review_id", "created_at"], unique=False)
    op.create_index(op.f("ix_review_messages_review_id"), "review_messages", ["review_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_messages_review_id"), table_name="review_messages")
    op.drop_index("ix_review_messages_review_created_at", table_name="review_messages")
    op.drop_index(op.f("ix_review_messages_author_role"), table_name="review_messages")
    op.drop_index(op.f("ix_review_messages_author_id"), table_name="review_messages")
    op.drop_table("review_messages")