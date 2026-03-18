"""cities + user.city_id + ad.city_id

Revision ID: f0ed9ec684df
Revises: 37b920a4a4d5
Create Date: 2026-03-01 13:22:04.561109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f0ed9ec684df'
down_revision: Union[str, None] = '37b920a4a4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) cities
    op.create_table(
        "cities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cities_slug", "cities", ["slug"], unique=True)

    # 2) add city_id to users
    op.add_column("users", sa.Column("city_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_city_id", "users", ["city_id"])
    op.create_foreign_key(
        "fk_users_city_id",
        "users",
        "cities",
        ["city_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3) add city_id to ads
    op.add_column("ads", sa.Column("city_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_ads_city_id", "ads", ["city_id"])
    op.create_foreign_key(
        "fk_ads_city_id",
        "ads",
        "cities",
        ["city_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4) seed: Saint Petersburg (spb)
    # фиксированный UUID, чтобы можно было ссылаться
    spb_id = "00000000-0000-0000-0000-000000000001"
    op.execute(
        sa.text(
            """
            INSERT INTO cities (id, slug, title, is_active)
            VALUES (:id, :slug, :title, true)
            ON CONFLICT (slug) DO NOTHING
            """
        ).bindparams(id=spb_id, slug="spb", title="Санкт-Петербург")
    )


def downgrade() -> None:
    op.drop_constraint("fk_ads_city_id", "ads", type_="foreignkey")
    op.drop_index("ix_ads_city_id", table_name="ads")
    op.drop_column("ads", "city_id")

    op.drop_constraint("fk_users_city_id", "users", type_="foreignkey")
    op.drop_index("ix_users_city_id", table_name="users")
    op.drop_column("users", "city_id")

    op.drop_index("ix_cities_slug", table_name="cities")
    op.drop_table("cities")
