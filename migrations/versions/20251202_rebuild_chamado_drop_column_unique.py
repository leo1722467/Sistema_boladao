"""
Rebuild chamado to remove column-level unique on numero and enforce (empresa_id, numero) unique.
SQLite requires table rebuild to drop autoindexes.
"""

from alembic import op
import sqlalchemy as sa

revision = '20251202_rebuild_chamado_drop_column_unique'
down_revision = '20251202_update_chamado_unique_numero_scope'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    # Create new table without column-level unique and with composite unique
    conn.execute(sa.text(
        """
        CREATE TABLE chamado_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL,
            empresa_id INTEGER,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status_id INTEGER,
            prioridade_id INTEGER,
            ultima_atualizacao DATETIME,
            requisitante_contato_id INTEGER,
            agente_contato_id INTEGER,
            proprietario_contato_id INTEGER,
            categoria_id INTEGER,
            ativo_id INTEGER,
            criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fechado_em DATETIME,
            origem_os_pendencia_id INTEGER,
            origem TEXT,
            UNIQUE (empresa_id, numero),
            FOREIGN KEY (empresa_id) REFERENCES empresa (id),
            FOREIGN KEY (status_id) REFERENCES status_chamado (id),
            FOREIGN KEY (prioridade_id) REFERENCES prioridade (id),
            FOREIGN KEY (requisitante_contato_id) REFERENCES contato (id),
            FOREIGN KEY (agente_contato_id) REFERENCES contato (id),
            FOREIGN KEY (proprietario_contato_id) REFERENCES contato (id),
            FOREIGN KEY (categoria_id) REFERENCES chamado_categoria (id),
            FOREIGN KEY (ativo_id) REFERENCES ativo (id),
            FOREIGN KEY (origem_os_pendencia_id) REFERENCES ordem_servico (id)
        )
        """
    ))

    # Copy data
    conn.execute(sa.text(
        """
        INSERT INTO chamado_new (
            id, numero, empresa_id, titulo, descricao, status_id, prioridade_id,
            ultima_atualizacao, requisitante_contato_id, agente_contato_id, proprietario_contato_id,
            categoria_id, ativo_id, criado_em, atualizado_em, fechado_em, origem_os_pendencia_id, origem
        )
        SELECT id, numero, empresa_id, titulo, descricao, status_id, prioridade_id,
               ultima_atualizacao, requisitante_contato_id, agente_contato_id, proprietario_contato_id,
               categoria_id, ativo_id, criado_em, atualizado_em, fechado_em, origem_os_pendencia_id, origem
        FROM chamado
        """
    ))

    # Drop old table and rename
    conn.execute(sa.text("DROP TABLE chamado"))
    conn.execute(sa.text("ALTER TABLE chamado_new RENAME TO chamado"))

    # Recreate index on id to match previous naming convention if needed
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix__chamado_id ON chamado (id)"))


def downgrade():
    # No reliable downgrade in SQLite for recreating autoindex; skipping
    pass

