"""initial registry schema

Revision ID: 0001_initial_registry
Revises:
Create Date: 2026-04-18 00:00:00

Establishes the registry database at v1. One table: ``companies``, keyed
by the slug that also names the on-disk SQLite file.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_registry"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "entity_type",
            sa.String(length=32),
            nullable=False,
            server_default="schedule_c",
        ),
        sa.Column(
            "tax_basis",
            sa.String(length=16),
            nullable=False,
            server_default="cash",
        ),
        sa.Column(
            "base_currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "fiscal_year_start",
            sa.String(length=5),
            nullable=False,
            server_default="01-01",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )


def downgrade() -> None:
    op.drop_table("companies")
