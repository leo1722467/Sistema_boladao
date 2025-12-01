"""Add chamado_defeito table

Revision ID: 20251201_add_chamado_defeito
Revises: 000000000001
Create Date: 2025-12-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251201_add_chamado_defeito'
down_revision = '000000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chamado_defeito',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('tipo_ativo_id', sa.Integer(), nullable=False),
    )

    try:
        op.create_index(op.f('ix__chamado_defeito__tipo_ativo_id'), 'chamado_defeito', ['tipo_ativo_id'])
    except Exception:
        pass

    try:
        op.create_unique_constraint('uq_chamado_defeito_tipo_nome', 'chamado_defeito', ['tipo_ativo_id', 'nome'])
    except Exception:
        pass

    try:
        op.create_foreign_key(
            op.f('fk__chamado_defeito__tipo_ativo_id__tipo_ativo'),
            'chamado_defeito', 'tipo_ativo', ['tipo_ativo_id'], ['id']
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_constraint(op.f('fk__chamado_defeito__tipo_ativo_id__tipo_ativo'), 'chamado_defeito', type_='foreignkey')
    except Exception:
        pass

    try:
        op.drop_constraint('uq_chamado_defeito_tipo_nome', 'chamado_defeito', type_='unique')
    except Exception:
        pass

    try:
        op.drop_index(op.f('ix__chamado_defeito__tipo_ativo_id'), table_name='chamado_defeito')
    except Exception:
        pass

    op.drop_table('chamado_defeito')

