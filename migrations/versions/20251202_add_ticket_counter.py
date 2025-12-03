"""
Add ticket_counter table for per-empresa global sequential numbering.
"""

from alembic import op
import sqlalchemy as sa

revision = '20251202_add_ticket_counter'
down_revision = '20251202_rebuild_chamado_drop_column_unique'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'ticket_counter',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('empresa_id', name='uq_ticket_counter_empresa'),
    )
    op.create_index('ix_ticket_counter_empresa_id', 'ticket_counter', ['empresa_id'])


def downgrade():
    op.drop_index('ix_ticket_counter_empresa_id', table_name='ticket_counter')
    op.drop_table('ticket_counter')

