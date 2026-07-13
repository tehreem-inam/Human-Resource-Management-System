"""fix leave request employee relations

Revision ID: 3f448013f96e
Revises: d041f9fff3d5
Create Date: 2026-02-16 18:12:46.729017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f448013f96e'
down_revision: Union[str, Sequence[str], None] = 'd041f9fff3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
