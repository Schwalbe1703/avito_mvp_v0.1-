"""update category titles

Revision ID: 8aa6cbdf03db
Revises: b5e60d081c7c
Create Date: 2026-02-23 10:14:03.808985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8aa6cbdf03db"
down_revision: Union[str, None] = "b5e60d081c7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_TITLES = {
    "fridge": "Холодильники",
    "wash": "Стиральные машины",
    "stove": "Плиты",
    "small": "Мелкая техника",
    "electric": "Электрика",
    "plumb": "Сантехника",
    "repair": "Ремонт",
    "it": "IT / Компьютеры",
}

NEW_TITLES = {
    "fridge": "Холодильники и кондиционеры",
    "wash": "Стиральные, сушильные, посудомоечные машины",
    "stove": "Плиты, духовки",
    "small": "Мелкая бытовая техника",
    "electric": "Электрика",
    "plumb": "Сантехника",
    "repair": "Мелкий бытовой ремонт",
    "it": "Создание сайтов и приложений",
}


def upgrade() -> None:
    bind = op.get_bind()
    for slug, title in NEW_TITLES.items():
        bind.execute(
            sa.text("UPDATE categories SET title = :title WHERE slug = :slug"),
            {"slug": slug, "title": title},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for slug, title in OLD_TITLES.items():
        bind.execute(
            sa.text("UPDATE categories SET title = :title WHERE slug = :slug"),
            {"slug": slug, "title": title},
        )
