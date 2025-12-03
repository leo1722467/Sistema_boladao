import asyncio
from app.db.session import SessionLocal
from app.services.ticket import TicketService

async def main():
    async with SessionLocal() as session:  # type: ignore
        svc = TicketService()
        t1 = await svc.create_with_asset(session=session, empresa_id=1, titulo="Test WEB", descricao="", origem="web")
        t2 = await svc.create_with_asset(session=session, empresa_id=1, titulo="Test WEB 2", descricao="", origem="web")
        t3 = await svc.create_with_asset(session=session, empresa_id=1, titulo="Test WPP", descricao="", origem="wpp")
        t4 = await svc.create_with_asset(session=session, empresa_id=4, titulo="Test WEB 4", descricao="", origem="web")
        t5 = await svc.create_with_asset(session=session, empresa_id=4, titulo="Test WPP 4", descricao="", origem="wpp")
        await session.commit()
        print({"t1": t1.numero, "t2": t2.numero, "t3": t3.numero, "t4": t4.numero, "t5": t5.numero})

if __name__ == "__main__":
    asyncio.run(main())
