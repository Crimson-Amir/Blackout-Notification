"""create tables

Revision ID: 5e9cb9f41dff
Revises: ddd8dd5fef62
Create Date: 2025-08-23 19:18:40.898877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e9cb9f41dff'
down_revision: Union[str, Sequence[str], None] = 'ddd8dd5fef62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.drop_table("user_service")

    op.create_table(
        "user_service",
        sa.Column("chat_id", sa.BigInteger, sa.ForeignKey("user_detail.chat_id"), primary_key=True),
        sa.Column("bill_id", sa.String, sa.ForeignKey("service.bill_id"), primary_key=True),
    )


def downgrade():
    op.drop_table("user_service")