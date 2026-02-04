import asyncio
import jwt
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from app.main import app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.models import UserAuth, Contato, OrdemServico, TipoOS


def gen_token(user_id: int) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": int((datetime.utcnow() + timedelta(minutes=60)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm="HS256")


async def ensure_user():
    async with SessionLocal() as session:  # type: ignore
        u = await session.get(UserAuth, 1)
        if not u:
            contato = Contato(nome="Tester", email="tester@example.com")
            session.add(contato)
            await session.flush()
            u = UserAuth(id=1, contato_id=contato.id, ativo=True)
            session.add(u)
        await session.commit()


async def ensure_os():
    async with SessionLocal() as session:  # type: ignore
        from sqlalchemy import select
        res = await session.execute(select(TipoOS).where(TipoOS.nome == "Teste"))
        t = res.scalars().first()
        if not t:
            t = TipoOS(nome="Teste")
            session.add(t)
            await session.flush()
        os_row = OrdemServico(tipo_os_id=t.id, numero_os=f"OS-{int(datetime.utcnow().timestamp())}")
        session.add(os_row)
        await session.commit()
        return os_row.id


def test_pendencias_flow(client, os_id, headers):
    p = {
        "tag": "PEND-001",
        "os_origem_id": os_id,
        "descricao": "Teste pendência",
        "status": "aberta",
    }
    r = client.post("/api/helpdesk/pendencias", json=p, headers=headers)
    assert r.status_code == 200
    pend = r.json()
    rlist = client.get("/api/helpdesk/pendencias?search=PEND-001", headers=headers)
    assert rlist.status_code == 200
    items = rlist.json()["pendencias"]
    assert len(items) >= 1
    pid = items[0]["id"]
    rupd = client.put(f"/api/helpdesk/pendencias/{pid}", json={"status": "em_atendimento"}, headers=headers)
    assert rupd.status_code == 200
    rlink = client.post(f"/api/helpdesk/service-orders/{os_id}/pendencias/resolve", json={"pendencia_ids": [pid], "close_pendencias": True}, headers=headers)
    assert rlink.status_code == 200
    rlinked = client.get(f"/api/helpdesk/service-orders/{os_id}/pendencias", headers=headers)
    assert rlinked.status_code == 200
    items = rlinked.json()["pendencias"]
    assert any(x["id"] == pid for x in items)


def main():
    asyncio.get_event_loop().run_until_complete(ensure_user())
    os_id = asyncio.get_event_loop().run_until_complete(ensure_os())
    token = gen_token(1)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    test_pendencias_flow(client, os_id, headers)
    print("OK")


if __name__ == "__main__":
    main()
