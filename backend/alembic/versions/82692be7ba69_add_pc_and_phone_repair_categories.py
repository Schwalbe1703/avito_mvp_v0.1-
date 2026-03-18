"""add pc and phone repair categories

Revision ID: 82692be7ba69
Revises: 8aa6cbdf03db
Create Date: 2026-02-23 10:46:07.154598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "82692be7ba69"
down_revision: Union[str, None] = "8aa6cbdf03db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CATEGORIES = [
    ("pc_repair", "Ремонт компьютеров и ноутбуков"),
    ("phone_repair", "Ремонт телефонов"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for slug, title in NEW_CATEGORIES:
        bind.execute(
            sa.text(
                """
                INSERT INTO categories (id, slug, title, created_at)
                VALUES (gen_random_uuid(), :slug, :title, now())
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {"slug": slug, "title": title},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM categories WHERE slug = ANY(:slugs)"),
        {"slugs": [c[0] for c in NEW_CATEGORIES]},
    )