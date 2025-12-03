"""
Update Chamado unique constraint: scope numero by empresa_id.
"""

from alembic import op
import sqlalchemy as sa

revision = '20251202_update_chamado_unique_numero_scope'
down_revision = '20251202_add_ticket_sequence_and_origem'
branch_labels = None
depends_on = None

def upgrade():
    # Use batch operations for SQLite
    with op.batch_alter_table('chamado') as batch_op:
        # Remove column-level unique from numero by altering column definition
        try:
            batch_op.alter_column(
                'numero',
                existing_type=sa.Text(),
                nullable=False,
                existing_nullable=False,
                existing_unique=True,
                unique=False,
            )
        except Exception:
            pass
        # Create composite unique on (empresa_id, numero)
        batch_op.create_unique_constraint('uq_chamado_empresa_numero', ['empresa_id', 'numero'])


def downgrade():
    with op.batch_alter_table('chamado') as batch_op:
        try:
            batch_op.drop_constraint('uq_chamado_empresa_numero', type_='unique')
        except Exception:
            pass
        # Recreate single-column unique if needed
        try:
            batch_op.create_unique_constraint('uq__chamado__numero', ['numero'])
        except Exception:
            pass
