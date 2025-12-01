"""Add serial_text to ativo table

Revision ID: 20251124_add_serial_text_to_ativo
Revises: 000000000001
Create Date: 2025-11-24
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251124_add_serial_text_to_ativo'
down_revision = '000000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add serial_text column (allow NULLs initially for existing rows)
    op.add_column('ativo', sa.Column('serial_text', sa.Text(), nullable=True))

    # Create unique constraint per empresa + serial_text
    try:
        op.create_unique_constraint('uq_ativo_empresa_serial', 'ativo', ['empresa_id', 'serial_text'])
    except Exception:
        pass


def downgrade() -> None:
    # Drop unique constraint if present
    try:
        op.drop_constraint('uq_ativo_empresa_serial', 'ativo', type_='unique')
    except Exception:
        pass

    # Drop the column
    op.drop_column('ativo', 'serial_text')