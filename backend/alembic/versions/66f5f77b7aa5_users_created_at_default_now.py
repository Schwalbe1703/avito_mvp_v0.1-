"""users created_at default now

Revision ID: 66f5f77b7aa5
Revises: 878f4b284d50
Create Date: 2026-02-21 14:12:38.463528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66f5f77b7aa5'
down_revision: Union[str, None] = '878f4b284d50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now();")

def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN created_at DROP DEFAULT;")
