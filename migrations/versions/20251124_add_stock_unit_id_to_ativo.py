"""Add stock_unit_id to ativo table

Revision ID: 20251124_add_stock_unit_id_to_ativo
Revises: 000000000001
Create Date: 2025-11-24
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251124_add_stock_unit_id_to_ativo'
down_revision = '000000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable column for linking to estoque
    op.add_column('ativo', sa.Column('stock_unit_id', sa.Integer(), nullable=True))

    # Create unique constraint to match model definition
    try:
        op.create_unique_constraint(op.f('uq__ativo__stock_unit_id'), 'ativo', ['stock_unit_id'])
    except Exception:
        # Constraint might already exist or not supported in this dialect
        pass

    # Create foreign key to estoque.id (best-effort; SQLite may ignore FKs on existing tables)
    try:
        op.create_foreign_key(
            op.f('fk__ativo__stock_unit_id__estoque'),
            'ativo', 'estoque', ['stock_unit_id'], ['id'], ondelete='SET NULL'
        )
    except Exception:
        pass


def downgrade() -> None:
    # Drop FK if present
    try:
        op.drop_constraint(op.f('fk__ativo__stock_unit_id__estoque'), 'ativo', type_='foreignkey')
    except Exception:
        pass

    # Drop unique constraint if present
    try:
        op.drop_constraint(op.f('uq__ativo__stock_unit_id'), 'ativo', type_='unique')
    except Exception:
        pass

    # Finally drop the column
    op.drop_column('ativo', 'stock_unit_id')