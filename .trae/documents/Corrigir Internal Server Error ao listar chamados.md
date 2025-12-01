## Causa Provável
- O 500 ocorre ao construir a resposta do ticket, acessando relacionamentos `status`, `prioridade`, `categoria`, `requisitante` e `agente` com carregamento preguiçoso em SQLAlchemy assíncrono, gerando erro de lazy-load/greenlet.
- Em `list_tickets`, os tickets são retornados via `select(Chamado)` sem `options(selectinload(...))`; em seguida `_build_ticket_detail_response` acessa os relacionamentos e dispara IO implícito (não suportado no async), quebrando o servidor.

## Alterações Propostas (Backend)
1. Eager loading na listagem:
- Em `app/services/ticket.py:262 list_tickets`, adicionar `selectinload` para: `Chamado.status`, `Chamado.prioridade`, `Chamado.categoria`, `Chamado.requisitante`, `Chamado.agente`, `Chamado.comentarios`.
- Manter filtros/paginação; apenas incluir `.options(...)` no `select`.

2. Garantir relações carregadas após criação:
- Em `app/api/helpdesk.py` na `create_ticket`, após `await session.commit()`, executar `await session.refresh(ticket, ['status','prioridade','categoria','requisitante','agente'])` antes de chamar `_build_ticket_detail_response`.

3. Robustez no builder:
- Em `_build_ticket_detail_response`, manter os checks já existentes e evitar acessos não guardados.

## Validação
1. Criar/associar empresa ao usuário de teste (via rotas admin) e confirmar que `TenantContext` resolve `empresa_id`.
2. Criar chamado via `POST /api/helpdesk/tickets` com `status='open'` e `priority='normal'`.
3. Listar via `GET /api/helpdesk/tickets?page=1&limit=20` autenticado com o mesmo usuário; verificar retorno 200 e presença do chamado.
4. Abrir a página `/tickets` autenticado; confirmar que a lista carrega sem erros e mostra o chamado recém-criado.

## Observações
- Não altera contratos de API; apenas corrige carregamento assíncrono para evitar 500.
- Mantém a regra para `requester` listar somente seus próprios chamados.

Confirma que posso aplicar essas mudanças e executar a validação descrita?