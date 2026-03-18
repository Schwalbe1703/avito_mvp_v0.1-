"""seed categories

Revision ID: b5e60d081c7c
Revises: d271e5910059
Create Date: 2026-02-23 10:00:01.378146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b5e60d081c7c"
down_revision: Union[str, None] = "d271e5910059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORIES = [
    ("fridge", "Холодильники"),
    ("wash", "Стиральные машины"),
    ("stove", "Плиты"),
    ("small", "Мелкая техника"),
    ("electric", "Электрика"),
    ("plumb", "Сантехника"),
    ("repair", "Ремонт"),
    ("it", "IT / Компьютеры"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Нужно для gen_random_uuid()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    for slug, title in CATEGORIES:
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
        {"slugs": [c[0] for c in CATEGORIES]},
    )