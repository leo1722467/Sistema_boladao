import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json
import sys
import time

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────

OLD_EMAIL    = "leonardoandrade@samserv.com.br"
OLD_PASSWORD = "Leo192@tb"
OLD_BASE     = "https://www.samserv.com.br/samserv/public/admin"

NEW_BASE     = "http://localhost:8081"
NEW_EMAIL    = "dev@example.com"      # ← ALTERE
NEW_PASSWORD = "secret123"              # ← ALTERE

# Mapeamentos baseados na planilha + HTML real
STATUS_MAP = {
    "aberto": 1,
    "em atendimento": 2,
    "pendente cliente": 3,
    "pendente": 3,
    "incidente": 4,
    "concluído": 5,
    "concluido": 5,
    "atendimento pausado": 6,
}

PRIORIDADE_MAP = {
    "baixa": 1,
    "media": 2,
    "média": 2,
    "alta": 3,
    "urgente": 4,
}

CATEGORIA_MAP = {
    "controle de acessos": 1,
    "cftv": 2,
    "motor": 3,
    "motores": 3,
    "ocr": 4,
    "requisição": 6,      # importante — apareceu no HTML
    "outros": 5,
}

PROPRIETARIO_MAP = {
    "cftv santos": 3,
    "portaria central": 4,
    "luiz fernando de souza": 5,
    "luiz fernando": 5,
    "alícia mirella": 6,
    "alicia mirella": 6,
    "sandro souza": 7,
}

AGENTE_FIXO_ID = 5          # Luiz Fernando de Souza (fixo conforme planilha)
EMPRESA_ID     = 1

STATUS_INTERESSE = ["aberto", "em atendimento", "pendente cliente", "pendente"]

# ─── FUNÇÕES AUXILIARES ──────────────────────────────────────────────────────

def login_antigo():
    s = requests.Session()
    login_url = f"{OLD_BASE}/login"
    r = s.get(login_url)
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "_token"})["value"]

    payload = {"_token": token, "email": OLD_EMAIL, "password": OLD_PASSWORD}
    r = s.post(login_url, data=payload)
    if "login" in r.url:
        print("❌ Falha no login antigo")
        sys.exit(1)
    print("✓ Logado no Samserv antigo")
    return s

def login_novo():
    r = requests.post(f"{NEW_BASE}/auth/login", json={"email": NEW_EMAIL, "password": NEW_PASSWORD})
    if r.status_code != 200:
        print("❌ Falha login novo:", r.text)
        sys.exit(1)
    token = r.json().get("access_token")
    print("✓ Logado no novo sistema")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def obter_chamados_relevantes(session_antigo):
    url = f"{OLD_BASE}/admin/tickets/data"
    r = session_antigo.get(url)
    if r.status_code != 200:
        print(f"❌ Falha ao obter lista: {r.status_code} - {r.text[:200]}")
        return []

    try:
        data = r.json()
        rows = data.get("data", [])
    except Exception as e:
        print(f"❌ Resposta não é JSON: {e}")
        print("Resposta bruta:", r.text[:500])
        return []

    chamados = []
    
    for row in rows:
        if not isinstance(row, dict):
            print("Row inesperado (não dict):", row)
            continue

        # Extrai status limpo (remove HTML do badge)
        status_html = row.get("status", "")
        soup_status = BeautifulSoup(status_html, "html.parser")
        status_texto = soup_status.get_text(strip=True).lower()

        if status_texto not in STATUS_INTERESSE:
            continue  # ignora se não for aberto/pendente/etc

        chamados.append({
            "numero": str(row.get("id", "")).lstrip("0"),
            "titulo": BeautifulSoup(row.get("subject", ""), "html.parser").get_text(strip=True),
            "status": status_texto,
            "ultima_atualizacao": str(row.get("updated_at", "")).strip(),
            "agente": str(row.get("agent", "")).strip().lower(),
            "prioridade": BeautifulSoup(row.get("priority", ""), "html.parser").get_text(strip=True).upper(),
            "proprietario": str(row.get("owner", "")).strip(),
            "categoria": BeautifulSoup(row.get("category", ""), "html.parser").get_text(strip=True),
            "agent_id": row.get("agent_id"),  # útil para futuro
        })

    print(f"Encontrados {len(chamados)} chamados relevantes (abertos/pendentes)")
    return chamados

def obter_detalhes(session_antigo, numero):
    url = f"{OLD_BASE}/admin/tickets/{numero}"
    r = session_antigo.get(url)
    if r.status_code != 200:
        return {"descricao": "(detalhe não acessível)", "criado_em": ""}

    soup = BeautifulSoup(r.text, "html.parser")

    # Descrição
    textarea = soup.find("textarea", {"name": "content"})
    desc = textarea.get_text(strip=True) if textarea else "(sem descrição)"

    # Data criação (mais robusto)
    criado_em = ""
    for strong in soup.find_all("strong"):
        if "Criado" in strong.get_text(strip=True):
            b = strong.find_next("b")
            if b:
                criado_em = b.get_text(strip=True)
                break

    return {"descricao": desc, "criado_em": criado_em}

def extrair_tag_ativo(titulo):
    m = re.search(r'\{([^}]+)\}', titulo)
    return m.group(1).strip() if m else None

def buscar_ativo_id(headers, tag):
    """
    Busca um ativo pela tag e retorna uma tupla:
    (ativo_id, categoria_id)
    
    - ativo_id: ID do ativo encontrado
    - categoria_id: mapeado conforme o tipo do ativo
      1: Controle de acessos
      2: CFTV
      3: Motor
      4: OCR
      5: OUTROS (default)
    """
    if not tag:
        return None, 5  # sem tag → OUTROS

    r = requests.get(
        f"{NEW_BASE}/api/helpdesk/assets",
        headers=headers,
        params={"search": tag, "limit": 3}
    )
    
    if r.status_code != 200:
        print(f"   Falha busca ativo {tag}: {r.status_code} - {r.text[:200]}")
        return None, 5
    
    data = r.json()
    
    # Normaliza para lista de ativos
    if isinstance(data, list):
        assets = data
    elif isinstance(data, dict):
        assets = data.get("assets", []) or data.get("data", [])
    else:
        print(f"   Formato inesperado de /assets: {type(data)}")
        return None, 5
    
    tag_lower = tag.lower()
    
    for a in assets:
        if not isinstance(a, dict):
            continue
            
        asset_tag = str(a.get("tag", "")).lower()
        if tag_lower in asset_tag:
            asset_id = a.get("id")
            
            # Extrai o tipo
            tipo_obj = a.get("tipo", {})
            tipo_nome = str(tipo_obj.get("nome", "")).strip() if isinstance(tipo_obj, dict) else ""
            
            # Mapeia para categoria_id
            tipo_lower = tipo_nome.lower()
            categoria_map = {
                "controle de acessos": 1,
                "cftv": 2,
                "motor": 3,
                "ocr": 4,
            }
            categoria_id = categoria_map.get(tipo_lower, 5)  # default OUTROS
            
            print(f"   Ativo encontrado: ID={asset_id}, Tag={a.get('tag')}, Tipo='{tipo_nome}', Categoria ID={categoria_id}")
            return asset_id, categoria_id
    
    print(f"   Nenhum ativo encontrado para tag '{tag}' → usando categoria OUTROS (5)")
    return None, 5
    
def buscar_existente(headers, numero_antigo):
    """
    Busca ticket existente usando o número antigo (ex: "168" ou "SAM-168").
    """
    # Normaliza o número para busca (sem prefixo SAM, só o número puro)
    num_puro = numero_antigo.replace("SAM-", "").lstrip("0")
    busca_termos = [f"sam-{num_puro}", num_puro, f"[{num_puro}]"]  # variações comuns

    print(f"   → Buscando por: {busca_termos}")

    r = requests.get(
        f"{NEW_BASE}/api/helpdesk/tickets",
        headers=headers,
        params={"search": f"SAM-{num_puro}", "limit": 5}  # busca com prefixo
    )

    if r.status_code != 200:
        print(f"   → Erro na busca: {r.status_code} - {r.text[:300]}")
        return None

    data = r.json()
    tickets = data.get("tickets", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    print(f"   → Encontrados {len(tickets)} tickets na resposta")

    for t in tickets:
        if not isinstance(t, dict):
            continue

        titulo = str(t.get("titulo", "")).lower()
        descricao = str(t.get("descricao", "")).lower()
        txt = titulo + " " + descricao

        # Debug: mostra o título e descrição de cada ticket
        print(f"      Ticket {t.get('id')}: titulo='{titulo[:60]}...'")

        # Match mais flexível (ignora case e procura qualquer variação)
        for termo in busca_termos:
            termo_lower = termo.lower()
            if termo_lower in txt:
                print(f"      → Match encontrado com termo '{termo}'")
                return t

    print("   → Nenhum match encontrado")
    return None

# ... (manter as importações e configs anteriores)

def atualizar_existente(ticket_id, chamado_antigo, headers_novo):
    """Faz PUT no ticket existente se houver mudança relevante"""
    status_antigo = chamado_antigo["status"]
    prioridade_antigo = chamado_antigo["prioridade"].lower()

    # Payload mínimo - só o que mudou + comentário obrigatório
    payload = {"comment": (
        f"Atualização detectada no Samserv antigo ({chamado_antigo['numero']})\n"
        f"Status: {status_antigo}\n"
        f"Prioridade: {prioridade_antigo}\n"
        f"Data: {datetime.now():%Y-%m-%d %H:%M:%S}"
    )}

    # Comparar e adicionar apenas campos alterados (opcional - depende da API)
    # Se a API aceitar status/prioridade como texto, use assim:
    payload["status"] = status_antigo
    payload["prioridade"] = prioridade_antigo

    # Se a API exigir IDs numéricos:
    payload["status_id"] = STATUS_MAP.get(status_antigo, 1)
    payload["prioridade_id"] = PRIORIDADE_MAP.get(prioridade_antigo, 2)

    try:
        r = requests.put(
            f"{NEW_BASE}/api/helpdesk/tickets/{ticket_id}",
            headers=headers_novo,
            json=payload,
            timeout=15
        )
        
        if r.status_code in (200, 204):
            print(f"   ✓ Atualizado com sucesso (id {ticket_id}) - comentário adicionado")
        else:
            print(f"   ✗ Falha no PUT: {r.status_code} - {r.text[:400]}")
            print("   Payload enviado:", json.dumps(payload, indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"   Erro na atualização PUT: {e}")

def sincronizar_um(chamado, session_antigo, headers_novo):
    num = chamado["numero"]
    print(f"\n→ Processando {num} | {chamado['titulo'][:60]}...")

    detalhes = obter_detalhes(session_antigo, num)
    chamado.update(detalhes)

    existente = buscar_existente(headers_novo, f"SAM-{num}")
    
    if existente:
        ticket_id = existente.get("id")
        print(f"   Já existe (id {ticket_id}) → verificando necessidade de atualização")

        # Lógica simples de comparação (pode expandir com mais campos)
        status_atual_novo = existente.get("status", "").lower()
        prioridade_atual_novo = existente.get("prioridade", "").lower()

        status_antigo = chamado["status"]
        prioridade_antigo = chamado["prioridade"].lower()

        precisa_atualizar = (
            status_atual_novo != status_antigo or
            prioridade_atual_novo != prioridade_antigo
        )

        if precisa_atualizar:
            print(f"   Mudança detectada → status antigo: {status_antigo}, prioridade: {prioridade_antigo}")
            atualizar_existente(ticket_id, chamado, headers_novo)
        else:
            print("   Sem mudanças relevantes → pulando atualização")
        
        return  # sai após tratar existente

    # Criação (se não existe)
    tag = extrair_tag_ativo(chamado["titulo"])
    ativo_id, categoria_ativo = buscar_ativo_id(headers_novo, tag) if tag else (None, None)
    payload = {
        "titulo": f"[SAM-{num}] {chamado['titulo']}",
        "descricao": chamado["descricao"] + f"\n\n--- Migrado em {datetime.now():%Y-%m-%d %H:%M} ---",
        "status": chamado["status"],           # texto (se API aceitar)
        "prioridade": chamado["prioridade"].lower(),
        "categoria": chamado["categoria"].lower(),
        "agente_contato_id": AGENTE_FIXO_ID,
        "proprietario_contato_id": PROPRIETARIO_MAP.get(chamado["proprietario"].lower()),
        "ativo_id": ativo_id,
        "origem": "Samserv",
        "categoria_id": categoria_ativo,
    }

    try:
        r = requests.post(
            f"{NEW_BASE}/api/helpdesk/tickets",
            headers=headers_novo,
            json=payload,
            timeout=15
        )
        
        if r.status_code in (200, 201):
            data = r.json()
            print(f"   ✓ Criado → {data.get('numero', data.get('id', 'sem número'))}")
        else:
            print(f"   ✗ Falha criação: {r.status_code} - {r.text[:400]}")
            print("   Payload enviado:", json.dumps(payload, indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"   Erro na requisição POST: {e}")
        
# ─── EXECUÇÃO ÚNICA (teste) ──────────────────────────────────────────────────

def main():
    print("=== SINCRONIZAÇÃO ÚNICA - Teste ===")
    print(f"Hora: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    s_antigo = login_antigo()
    h_novo   = login_novo()

    chamados = obter_chamados_relevantes(s_antigo)

    for ch in chamados[:5]:  # ← limitei a 5 para teste — remova o [:5] depois
        sincronizar_um(ch, s_antigo, h_novo)
        time.sleep(1.5)  # evitar sobrecarga

    print("\n=== Finalizado ===")

if __name__ == "__main__":
    main()