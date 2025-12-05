"""
Add helpdesk admin tables: routing rules, macros, SLA overrides, auto-close policy.
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = '20251205_add_helpdesk_admin_tables'
down_revision = '20251202_add_ticket_counter'
branch_labels = None
depends_on = None


def upgrade():
    # helpdesk_routing_rule
    op.create_table(
        'helpdesk_routing_rule',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column('prioridade_id', sa.Integer(), nullable=True),
        sa.Column('agente_contato_id', sa.Integer(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_helpdesk_routing_rule_empresa_id', 'helpdesk_routing_rule', ['empresa_id'])
    op.create_index('ix_helpdesk_routing_rule_categoria_id', 'helpdesk_routing_rule', ['categoria_id'])
    op.create_index('ix_helpdesk_routing_rule_prioridade_id', 'helpdesk_routing_rule', ['prioridade_id'])

    # helpdesk_macro
    op.create_table(
        'helpdesk_macro',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_helpdesk_macro_empresa_id', 'helpdesk_macro', ['empresa_id'])

    # helpdesk_sla_override
    op.create_table(
        'helpdesk_sla_override',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('prioridade_id', sa.Integer(), nullable=False),
        sa.Column('response_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('resolution_hours', sa.Integer(), nullable=False, server_default='72'),
        sa.Column('escalation_hours', sa.Integer(), nullable=False, server_default='48'),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_helpdesk_sla_override_empresa_id', 'helpdesk_sla_override', ['empresa_id'])
    op.create_index('ix_helpdesk_sla_override_prioridade_id', 'helpdesk_sla_override', ['prioridade_id'])

    # helpdesk_auto_close_policy
    op.create_table(
        'helpdesk_auto_close_policy',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('pending_customer_days', sa.Integer(), nullable=False, server_default='14'),
        sa.Column('resolved_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_helpdesk_auto_close_policy_empresa_id', 'helpdesk_auto_close_policy', ['empresa_id'])


def downgrade():
    op.drop_index('ix_helpdesk_auto_close_policy_empresa_id', table_name='helpdesk_auto_close_policy')
    op.drop_table('helpdesk_auto_close_policy')
    op.drop_index('ix_helpdesk_sla_override_prioridade_id', table_name='helpdesk_sla_override')
    op.drop_index('ix_helpdesk_sla_override_empresa_id', table_name='helpdesk_sla_override')
    op.drop_table('helpdesk_sla_override')
    op.drop_index('ix_helpdesk_macro_empresa_id', table_name='helpdesk_macro')
    op.drop_table('helpdesk_macro')
    op.drop_index('ix_helpdesk_routing_rule_prioridade_id', table_name='helpdesk_routing_rule')
    op.drop_index('ix_helpdesk_routing_rule_categoria_id', table_name='helpdesk_routing_rule')
    op.drop_index('ix_helpdesk_routing_rule_empresa_id', table_name='helpdesk_routing_rule')
    op.drop_table('helpdesk_routing_rule')

