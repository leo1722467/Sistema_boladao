from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from app.core.authorization import get_authorization_context, AuthorizationContext
from app.db.models import (
    HelpdeskRoutingRule,
    HelpdeskMacro,
    HelpdeskSLAOverride,
    HelpdeskAutoClosePolicy,
    StatusChamado,
    Chamado,
)
from app.core.helpdesk_config import load_notifications_config, save_notifications_config

router = APIRouter(prefix="/admin/helpdesk", tags=["admin"])

@router.get("/routing")
async def get_routing(auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    try:
        res = await session.execute(select(HelpdeskRoutingRule).where(HelpdeskRoutingRule.empresa_id == empresa_id))
        rules = [
            {
                "id": r.id,
                "categoria_id": r.categoria_id,
                "prioridade_id": r.prioridade_id,
                "agente_contato_id": r.agente_contato_id,
                "ativo": r.ativo,
            }
            for r in res.scalars().all()
        ]
    except Exception:
        rules = []
    return {"empresa_id": empresa_id, "rules": rules}

@router.put("/routing")
async def put_routing(payload: dict, auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    items = payload.get("rules", [])
    await session.execute(delete(HelpdeskRoutingRule).where(HelpdeskRoutingRule.empresa_id == empresa_id))
    for it in items:
        rule = HelpdeskRoutingRule(
            empresa_id=empresa_id,
            categoria_id=it.get("categoria_id"),
            prioridade_id=it.get("prioridade_id"),
            agente_contato_id=it.get("agente_contato_id"),
            ativo=bool(it.get("ativo", True)),
        )
        session.add(rule)
    await session.commit()
    return {"ok": True}

@router.get("/macros")
async def get_macros(auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    try:
        res = await session.execute(select(HelpdeskMacro).where(HelpdeskMacro.empresa_id == empresa_id))
        macros = [
            {
                "id": m.id,
                "nome": m.nome,
                "descricao": m.descricao,
                "actions": m.actions,
            }
            for m in res.scalars().all()
        ]
    except Exception:
        macros = []
    return {"empresa_id": empresa_id, "macros": macros}

@router.put("/macros")
async def put_macros(payload: dict, auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    items = payload.get("macros", [])
    await session.execute(delete(HelpdeskMacro).where(HelpdeskMacro.empresa_id == empresa_id))
    for it in items:
        macro = HelpdeskMacro(
            empresa_id=empresa_id,
            nome=it.get("nome") or "",
            descricao=it.get("descricao"),
            actions=it.get("actions") or {},
        )
        session.add(macro)
    await session.commit()
    return {"ok": True}

@router.get("/sla-overrides")
async def get_sla_overrides(auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    try:
        res = await session.execute(select(HelpdeskSLAOverride).where(HelpdeskSLAOverride.empresa_id == empresa_id))
        overrides = [
            {
                "id": o.id,
                "prioridade_id": o.prioridade_id,
                "response_hours": o.response_hours,
                "resolution_hours": o.resolution_hours,
                "escalation_hours": o.escalation_hours,
            }
            for o in res.scalars().all()
        ]
    except Exception:
        overrides = []
    return {"empresa_id": empresa_id, "overrides": overrides}

@router.put("/sla-overrides")
async def put_sla_overrides(payload: dict, auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    items = payload.get("overrides", [])
    await session.execute(delete(HelpdeskSLAOverride).where(HelpdeskSLAOverride.empresa_id == empresa_id))
    for it in items:
        ov = HelpdeskSLAOverride(
            empresa_id=empresa_id,
            prioridade_id=int(it.get("prioridade_id")),
            response_hours=int(it.get("response_hours", 24)),
            resolution_hours=int(it.get("resolution_hours", 72)),
            escalation_hours=int(it.get("escalation_hours", 48)),
        )
        session.add(ov)
    await session.commit()
    try:
        from app.services.notification_email import EmailNotifier
        from app.core.config import get_settings
        notifier = EmailNotifier()
        team = get_settings().NOTIFY_SLA_TEAM_EMAILS
        notifier.send_sla_overrides_updated(team, {"empresa_id": empresa_id})
    except Exception:
        pass
    return {"ok": True}

@router.get("/notifications")
async def get_notifications_config(_: AuthorizationContext = Depends(get_authorization_context)):
    return load_notifications_config()

@router.put("/notifications")
async def put_notifications_config(payload: dict, _: AuthorizationContext = Depends(get_authorization_context)):
    cfg = load_notifications_config()
    # Merge incoming payload with existing config
    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            else:
                a[k] = v
        return a
    cfg = merge(cfg, payload or {})
    save_notifications_config(cfg)
    return {"ok": True, "config": cfg}

@router.get("/auto-close")
async def get_auto_close_policy(auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    try:
        res = await session.execute(select(HelpdeskAutoClosePolicy).where(HelpdeskAutoClosePolicy.empresa_id == empresa_id))
        pol = res.scalars().first()
    except Exception:
        pol = None
    if not pol:
        return {"empresa_id": empresa_id, "enabled": False, "pending_customer_days": 14, "resolved_days": 7}
    return {"empresa_id": empresa_id, "enabled": pol.enabled, "pending_customer_days": pol.pending_customer_days, "resolved_days": pol.resolved_days}

@router.put("/auto-close")
async def put_auto_close_policy(payload: dict, auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    empresa_id = auth.tenant.empresa_id
    res = await session.execute(select(HelpdeskAutoClosePolicy).where(HelpdeskAutoClosePolicy.empresa_id == empresa_id))
    pol = res.scalars().first()
    if not pol:
        pol = HelpdeskAutoClosePolicy(empresa_id=empresa_id)
        session.add(pol)
    pol.enabled = bool(payload.get("enabled", pol.enabled))
    pol.pending_customer_days = int(payload.get("pending_customer_days", pol.pending_customer_days))
    pol.resolved_days = int(payload.get("resolved_days", pol.resolved_days))
    await session.commit()
    return {"ok": True}

@router.post("/run-auto-close")
async def run_auto_close(auth: AuthorizationContext = Depends(get_authorization_context), session: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    empresa_id = auth.tenant.empresa_id
    polres = await session.execute(select(HelpdeskAutoClosePolicy).where(HelpdeskAutoClosePolicy.empresa_id == empresa_id))
    pol = polres.scalars().first()
    if not pol or not pol.enabled:
        return {"closed": 0}
    pending_days = int(pol.pending_customer_days)
    resolved_days = int(pol.resolved_days)
    now = datetime.utcnow()
    status_rows = await session.execute(select(StatusChamado))
    statuses = {s.nome.strip().lower(): s for s in status_rows.scalars().all()}
    def _get(name: str):
        return statuses.get(name) or statuses.get(name.replace("_", " "))
    pending = _get("pending_customer") or _get("aguardando cliente") or _get("em espera")
    closed = _get("closed") or _get("fechado")
    resolved = _get("resolved") or _get("resolvido")
    if not closed:
        return {"closed": 0}
    q = select(Chamado).where(Chamado.empresa_id == empresa_id)
    res = await session.execute(q)
    tickets = res.scalars().all()
    count = 0
    for t in tickets:
        status_name = (t.status.nome if t.status else "").strip().lower()
        if pending and status_name in [pending.nome.strip().lower()] and t.atualizado_em and t.atualizado_em < now - timedelta(days=pending_days):
            t.status_id = closed.id
            count += 1
        if resolved and status_name in [resolved.nome.strip().lower()] and t.atualizado_em and t.atualizado_em < now - timedelta(days=resolved_days):
            t.status_id = closed.id
            count += 1
    await session.commit()
    return {"closed": count}
