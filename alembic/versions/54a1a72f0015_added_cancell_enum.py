"""added cancell enum

Revision ID: 54a1a72f0015
Revises: 9493600e3d40
Create Date: 2026-02-23 01:07:41.898534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '54a1a72f0015'
down_revision: Union[str, Sequence[str], None] = '9493600e3d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ENUM type name in your DB
enum_name = "leave_request_status_enum"

def upgrade():
    # Add new value 'cancelled' to the ENUM
    op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS 'cancelled';")


def downgrade():
    # Downgrading ENUMs is tricky; usually you can't remove a value safely
    pass