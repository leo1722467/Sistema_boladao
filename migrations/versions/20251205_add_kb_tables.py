"""
Add KB (Knowledge Base) tables: kb_category, kb_article.
"""

from alembic import op
import sqlalchemy as sa

revision = '20251205_add_kb_tables'
down_revision = '20251205_add_helpdesk_admin_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'kb_category',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_kb_category_empresa_id', 'kb_category', ['empresa_id'])

    op.create_table(
        'kb_article',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column('titulo', sa.Text(), nullable=False),
        sa.Column('resumo', sa.Text(), nullable=True),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('publicado', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('visibilidade', sa.Text(), nullable=False, server_default='external'),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['categoria_id'], ['kb_category.id']),
    )
    op.create_index('ix_kb_article_empresa_id', 'kb_article', ['empresa_id'])
    op.create_index('ix_kb_article_categoria_id', 'kb_article', ['categoria_id'])


def downgrade():
    op.drop_index('ix_kb_article_categoria_id', table_name='kb_article')
    op.drop_index('ix_kb_article_empresa_id', table_name='kb_article')
    op.drop_table('kb_article')
    op.drop_index('ix_kb_category_empresa_id', table_name='kb_category')
    op.drop_table('kb_category')

