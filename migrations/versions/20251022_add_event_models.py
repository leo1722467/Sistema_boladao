"""Add event models for outbox pattern

Revision ID: 20251022_add_event_models
Revises: 8e4d4b57efe1
Create Date: 2025-10-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20251022_add_event_models'
down_revision = '8e4d4b57efe1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add event models for outbox pattern and integrations."""
    
    # Create outbox_events table
    op.create_table('outbox_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_id', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    
    # Create indexes for outbox_events
    op.create_index(op.f('ix_outbox_events_id'), 'outbox_events', ['id'])
    op.create_index(op.f('ix_outbox_events_event_id'), 'outbox_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_outbox_events_event_type'), 'outbox_events', ['event_type'])
    op.create_index(op.f('ix_outbox_events_aggregate_id'), 'outbox_events', ['aggregate_id'])
    op.create_index(op.f('ix_outbox_events_status'), 'outbox_events', ['status'])
    op.create_index(op.f('ix_outbox_events_created_at'), 'outbox_events', ['created_at'])
    op.create_index(op.f('ix_outbox_events_next_retry_at'), 'outbox_events', ['next_retry_at'])
    op.create_index(op.f('ix_outbox_events_empresa_id'), 'outbox_events', ['empresa_id'])
    
    # Create webhook_endpoints table
    op.create_table('webhook_endpoints',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=True),
        sa.Column('event_types', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_endpoints'))
    )
    
    # Create indexes for webhook_endpoints
    op.create_index(op.f('ix_webhook_endpoints_id'), 'webhook_endpoints', ['id'])
    op.create_index(op.f('ix_webhook_endpoints_empresa_id'), 'webhook_endpoints', ['empresa_id'])
    
    # Create webhook_deliveries table
    op.create_table('webhook_deliveries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('webhook_endpoint_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('http_method', sa.String(length=10), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('response_headers', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_deliveries'))
    )
    
    # Create indexes for webhook_deliveries
    op.create_index(op.f('ix_webhook_deliveries_id'), 'webhook_deliveries', ['id'])
    op.create_index(op.f('ix_webhook_deliveries_webhook_endpoint_id'), 'webhook_deliveries', ['webhook_endpoint_id'])
    op.create_index(op.f('ix_webhook_deliveries_event_id'), 'webhook_deliveries', ['event_id'])
    op.create_index(op.f('ix_webhook_deliveries_attempted_at'), 'webhook_deliveries', ['attempted_at'])
    
    # Create integration_logs table
    op.create_table('integration_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('integration_type', sa.String(length=50), nullable=False),
        sa.Column('operation', sa.String(length=100), nullable=False),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('response_data', sa.JSON(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_logs'))
    )
    
    # Create indexes for integration_logs
    op.create_index(op.f('ix_integration_logs_id'), 'integration_logs', ['id'])
    op.create_index(op.f('ix_integration_logs_integration_type'), 'integration_logs', ['integration_type'])
    op.create_index(op.f('ix_integration_logs_empresa_id'), 'integration_logs', ['empresa_id'])
    op.create_index(op.f('ix_integration_logs_created_at'), 'integration_logs', ['created_at'])


def downgrade() -> None:
    """Remove event models and related tables."""
    
    # Drop indexes first
    op.drop_index(op.f('ix_integration_logs_created_at'), table_name='integration_logs')
    op.drop_index(op.f('ix_integration_logs_empresa_id'), table_name='integration_logs')
    op.drop_index(op.f('ix_integration_logs_integration_type'), table_name='integration_logs')
    op.drop_index(op.f('ix_integration_logs_id'), table_name='integration_logs')
    
    op.drop_index(op.f('ix_webhook_deliveries_attempted_at'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_event_id'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_webhook_endpoint_id'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_id'), table_name='webhook_deliveries')
    
    op.drop_index(op.f('ix_webhook_endpoints_empresa_id'), table_name='webhook_endpoints')
    op.drop_index(op.f('ix_webhook_endpoints_id'), table_name='webhook_endpoints')
    
    op.drop_index(op.f('ix_outbox_events_empresa_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_next_retry_at'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_created_at'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_status'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_aggregate_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_event_type'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_event_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_id'), table_name='outbox_events')
    
    # Drop tables
    op.drop_table('integration_logs')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')
    op.drop_table('outbox_events')