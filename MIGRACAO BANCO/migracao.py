import sqlite3
from datetime import datetime

APP_DB = "app.db"
HIST_DB = "historico.db"

OLD_TABLE = "equipamentos"   # historico.db
NEW_TABLE = "ativo"   # app.db

DEFAULT_CONTRATO_ID = 1
DEFAULT_EMPRESA_ID = 1
DEFAULT_INTERNO = 0

TIPO_MAP = {
    "controladores": 1,
    "cftv": 2,
    "motores": 3,
    "lpr": 4,
}

ACESSO_MAP = {
    "escada": 1,
    "pta": 2,
    "térreo": 3,
    "terreo": 3,
    "andaime": 4,
}

LOCAL_MAP = {
    "terminal": 1,
    "a29": 2,
}

def norm(v):
    if v is None:
        return None
    return str(v).strip().lower()

def to_int_or_none(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    # aceita "001" -> 1, mas rejeita "A29-1"
    if s.isdigit():
        return int(s)
    return None

def to_text_or_none(v):
    if v is None:
        return None
    return str(v)

def map_tipo(classe):
    k = norm(classe)
    return TIPO_MAP.get(k) if k else None

def map_acesso(acesso):
    k = norm(acesso)
    return ACESSO_MAP.get(k) if k else None

def map_local(local):
    k = norm(local)
    return LOCAL_MAP.get(k) if k else None

def main():
    con = sqlite3.connect(APP_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("PRAGMA foreign_keys=OFF;")
    cur.execute("BEGIN;")
    cur.execute("ATTACH DATABASE ? AS old;", (HIST_DB,))

    # tabela para guardar relação de ids quando o old.id não for numérico
    cur.execute("""
        CREATE TABLE IF NOT EXISTS migracao_id_map (
            old_id_text TEXT PRIMARY KEY,
            new_id_int  INTEGER NOT NULL,
            criado_em   DATETIME NOT NULL
        )
    """)

    rows = cur.execute(f"""
        SELECT
            id, tag, descricao,
            ativado, classe, acesso, local,
            periodicidade, data_instalacao
        FROM old.{OLD_TABLE}
    """).fetchall()

    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    # relatórios
    unmapped_tipo = {}
    unmapped_acesso = {}
    unmapped_local = {}
    non_numeric_ids = 0
    inserted = 0
    skipped = 0

    for r in rows:
        old_id_text = to_text_or_none(r["id"])
        old_id_int = to_int_or_none(r["id"])  # só vira int se for numérico

        payload = {
            "id": old_id_int,  # pode ser None
            "tag": to_text_or_none(r["tag"]),
            "descricao": to_text_or_none(r["descricao"]),
            "contrato_id": DEFAULT_CONTRATO_ID,
            "status_ativo_id": to_int_or_none(r["ativado"]),  # 0/1
            "tipo_ativo_id": map_tipo(r["classe"]),
            "acesso_ativo_id": map_acesso(r["acesso"]),
            "local_instalacao_id": map_local(r["local"]),
            "interno": to_int_or_none(DEFAULT_INTERNO),  # BOOLEAN -> 0/1
            "periodicidade": to_text_or_none(r["periodicidade"]),  # app é TEXT
            "data_instalacao": to_text_or_none(r["data_instalacao"]),  # app é DATETIME (aceita texto)
            "serial": None,        # mapeado como NULL
            "criado_em": now,      # datetime.now()
            "empresa_id": DEFAULT_EMPRESA_ID,
            "stock_unit_id": None,
            "serial_text": None,
        }

        # contabiliza dicionários não mapeados
        if payload["tipo_ativo_id"] is None and r["classe"] is not None:
            k = str(r["classe"])
            unmapped_tipo[k] = unmapped_tipo.get(k, 0) + 1

        if payload["acesso_ativo_id"] is None and r["acesso"] is not None:
            k = str(r["acesso"])
            unmapped_acesso[k] = unmapped_acesso.get(k, 0) + 1

        if payload["local_instalacao_id"] is None and r["local"] is not None:
            k = str(r["local"])
            unmapped_local[k] = unmapped_local.get(k, 0) + 1

        # Se o old.id for numérico, tentamos preservar o id
        if payload["id"] is not None:
            exists = cur.execute(
                f"SELECT 1 FROM main.{NEW_TABLE} WHERE id = ? LIMIT 1",
                (payload["id"],)
            ).fetchone()
            if exists:
                skipped += 1
                continue

            cur.execute(f"""
                INSERT INTO main.{NEW_TABLE} (
                    id, tag, descricao,
                    contrato_id, status_ativo_id,
                    tipo_ativo_id, acesso_ativo_id, local_instalacao_id,
                    interno, periodicidade, data_instalacao,
                    serial, criado_em, empresa_id,
                    stock_unit_id, serial_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload["id"], payload["tag"], payload["descricao"],
                payload["contrato_id"], payload["status_ativo_id"],
                payload["tipo_ativo_id"], payload["acesso_ativo_id"], payload["local_instalacao_id"],
                payload["interno"], payload["periodicidade"], payload["data_instalacao"],
                payload["serial"], payload["criado_em"], payload["empresa_id"],
                payload["stock_unit_id"], payload["serial_text"]
            ))
            inserted += 1

        else:
            # old.id NÃO é numérico -> deixa o SQLite gerar um novo id INTEGER
            non_numeric_ids += 1

            # evita duplicar por tag (se você quiser usar tag como “chave lógica”)
            # Se NÃO quiser essa proteção, apague este bloco.
            if payload["tag"]:
                exists_tag = cur.execute(
                    f"SELECT id FROM main.{NEW_TABLE} WHERE tag = ? LIMIT 1",
                    (payload["tag"],)
                ).fetchone()
                if exists_tag:
                    skipped += 1
                    # guarda o mapa mesmo assim
                    cur.execute("""
                        INSERT OR REPLACE INTO migracao_id_map (old_id_text, new_id_int, criado_em)
                        VALUES (?, ?, ?)
                    """, (old_id_text, int(exists_tag["id"]), now))
                    continue

            cur.execute(f"""
                INSERT INTO main.{NEW_TABLE} (
                    tag, descricao,
                    contrato_id, status_ativo_id,
                    tipo_ativo_id, acesso_ativo_id, local_instalacao_id,
                    interno, periodicidade, data_instalacao,
                    serial, criado_em, empresa_id,
                    stock_unit_id, serial_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload["tag"], payload["descricao"],
                payload["contrato_id"], payload["status_ativo_id"],
                payload["tipo_ativo_id"], payload["acesso_ativo_id"], payload["local_instalacao_id"],
                payload["interno"], payload["periodicidade"], payload["data_instalacao"],
                payload["serial"], payload["criado_em"], payload["empresa_id"],
                payload["stock_unit_id"], payload["serial_text"]
            ))

            new_id = cur.execute("SELECT last_insert_rowid() AS id;").fetchone()["id"]

            # salva relação old_id(texto) -> new_id(integer)
            cur.execute("""
                INSERT OR REPLACE INTO migracao_id_map (old_id_text, new_id_int, criado_em)
                VALUES (?, ?, ?)
            """, (old_id_text, int(new_id), now))

            inserted += 1

    con.commit()

    try:
        cur.execute("DETACH DATABASE old;")
    except sqlite3.OperationalError as e:
        print("Aviso: não foi possível dar DETACH no banco antigo:", e)

    con.close()


    print("=== MIGRAÇÃO CONCLUÍDA ===")
    print(f"Inseridos: {inserted}")
    print(f"Pulados: {skipped}")
    print(f"IDs não numéricos (geraram novo id): {non_numeric_ids}")
    print("\n--- NÃO MAPEADOS (revisar dicionários) ---")
    print("classe -> tipo_ativo_id:", unmapped_tipo or "OK")
    print("acesso -> acesso_ativo_id:", unmapped_acesso or "OK")
    print("local  -> local_instalacao_id:", unmapped_local or "OK")
    print("\nTabela de relação criada/atualizada: migracao_id_map")

if __name__ == "__main__":
    main()
