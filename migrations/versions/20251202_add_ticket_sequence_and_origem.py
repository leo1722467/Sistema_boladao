"""
Add ticket_sequence table and origem column to chamado.
"""

from alembic import op
import sqlalchemy as sa

revision = '20251202_add_ticket_sequence_and_origem'
down_revision = '20251201_add_chamado_defeito'
branch_labels = None
depends_on = None

def upgrade():
    # Add origem column to chamado
    try:
        op.add_column('chamado', sa.Column('origem', sa.Text(), nullable=True))
    except Exception:
        pass

    # Create ticket_sequence table
    op.create_table(
        'ticket_sequence',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('origin', sa.Text(), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('empresa_id', 'origin', name='uq_ticket_sequence_empresa_origin'),
    )
    op.create_index('ix_ticket_sequence_empresa_id', 'ticket_sequence', ['empresa_id'])


def downgrade():
    # Drop ticket_sequence table
    op.drop_index('ix_ticket_sequence_empresa_id', table_name='ticket_sequence')
    op.drop_table('ticket_sequence')
    # Remove origem column
    try:
        op.drop_column('chamado', 'origem')
    except Exception:
        pass

