# Developer Guide: Pages, Routes, and Data Integration

This guide explains how the project is structured and how to add new pages, routes, and their backend integrations quickly. It uses the existing Tickets page as a working example.

## Overview
- Framework: FastAPI for APIs and server-rendered pages via Jinja2 templates.
- Entry point: `app/main.py` creates the app, wires routers, mounts static assets, and configures middlewares.
- Web pages: `app/web/router.py` (general) and `app/web/admin_router.py` (admin under `/admin`).
- APIs: `app/api/*.py` (e.g., `helpdesk.py`, `admin.py`, `integrations.py`).
- Templates: `app/web/templates/` (admin templates in `app/web/templates/admin/`).
- Static assets: `app/web/static/` mounted to `/static`.
- Auth: Login sets cookie `access_token`; middleware gates protected paths and API calls.

## Windows Shell Conventions (Command Prompt)
- Use Command Prompt (`cmd`) instead of PowerShell for Windows examples.
- Activate venv:
  ```cmd
  .\.venv\Scripts\activate
  ```
- Set environment variables:
  ```cmd
  set APP_DB_URL=sqlite+aiosqlite:///./app.db
  set APP_JWT_SECRET=change-me
  set APP_APP_PORT=8081
  ```
- Run migrations:
  ```cmd
  alembic upgrade head
  ```
- Call APIs using `curl`:
  ```cmd
  curl -X POST ^
    -H "Content-Type: application/json" ^
    -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}" ^
    http://localhost:8081/auth/login
  ```

## App Startup and Middleware
- `app/main.py` adds middlewares:
  - `RequestIDMiddleware` and `SecurityHeadersMiddleware` for traceability and security headers.
  - `SecurityMiddleware` for rate limiting/vulnerability scanning.
  - `AuthenticationMiddleware` to protect web and API routes.
- Public paths: `/`, `/web/login`, `/auth`, `/static`, docs.
- Protected paths: `/dashboard`, `/admin`; API prefixes: `/api`, `/admin/api`.
- Behavior:
  - API without auth → `401` JSON.
  - Web without auth → redirect to `/` (login).

## Web Routing and Templates
- Web routes live in `app/web/router.py` and return `TemplateResponse`:
  ```py
  @router.get("/tickets", response_class=HTMLResponse)
  async def tickets_page(request: Request) -> HTMLResponse:
      return templates.TemplateResponse("tickets.html", {"request": request})
  ```
- Admin pages are namespaced in `app/web/admin_router.py` and templates under `templates/admin/`.
- Protect web routes server-side by adding `Depends(get_current_user_any)` or configure `AuthenticationMiddleware.protected_paths`.

## Example: Tickets Page
- Route: `GET /tickets` in `app/web/router.py` → `tickets.html`.
- Template: `app/web/templates/tickets.html` fetches data from APIs:
  - List tickets: `GET /api/helpdesk/tickets`.
  - Ticket detail: `GET /api/helpdesk/tickets/{id}`.
- API implementation: `app/api/helpdesk.py` under prefix `/api/helpdesk` uses services in `app/services/ticket.py` and repositories.

## Add a New Page (General)
1) Create the template
   - File: `app/web/templates/<your_page>.html`
   - Always pass the request: `{"request": request}` in the route.
   - Reference assets via `/static/...` (mounted in `main.py`).

2) Add the route
   - In `app/web/router.py`:
     ```py
     @router.get("/reports", response_class=HTMLResponse)
     async def reports_page(request: Request, _: object = Depends(get_current_user_any)) -> HTMLResponse:
         return templates.TemplateResponse("reports.html", {"request": request})
     ```
   - Use `Depends(get_current_user_any)` to require authentication.

3) Build APIs for dynamic data (optional)
   - Create `app/api/reports.py`:
     ```py
     from fastapi import APIRouter, Depends
     from sqlalchemy.ext.asyncio import AsyncSession
     from app.db.session import get_db
     router = APIRouter(prefix="/api/reports", tags=["reports"])

     @router.get("/summary")
     async def summary(session: AsyncSession = Depends(get_db)):
         return {"total": 42, "by_month": {"2025-01": 10}}
     ```
   - Include the router in `app/main.py` with `app.include_router(...)` (import your router).

4) Consume API from the template
   - In `reports.html`:
     ```html
     <script>
       async function loadSummary() {
         const res = await fetch('/api/reports/summary');
         const data = await res.json();
         // render data into the page
       }
       loadSummary();
     </script>
     ```

5) Add navigation
   - Update your header/sidebar markup to link to `/reports` (mirror patterns from `dashboard.html`/`tickets.html`).

## Add an Admin Page
1) Template: `app/web/templates/admin/<feature>.html`
2) Route in `app/web/admin_router.py`:
   ```py
   @router.get("/reports", response_class=HTMLResponse)
   async def admin_reports(request: Request, _: object = Depends(get_current_user_any)) -> HTMLResponse:
       return templates.TemplateResponse("admin/reports.html", {"request": request})
   ```
3) Admin APIs can live in `app/api/admin.py` or a new file with prefix `/admin/...`.

## Services, Repositories, and Schemas
- Services (`app/services/*`) orchestrate business logic.
- Repositories (`app/repositories/*`) handle SQLAlchemy persistence.
- Schemas (`app/schemas/*`) define request/response DTOs.
- Typical API flow:
  - Auth/tenant context via dependencies.
  - `AsyncSession` from `get_db`.
  - Service calls repository, returns DTOs.

## Static Assets
- Place JS/CSS/images in `app/web/static/`.
- Reference in HTML: `/static/...`.

## Running Locally (Command Prompt)
- Install deps: `pip install -r requirements.txt`
- Start dev server:
  - `python -m uvicorn app.main:app --reload`
  - or `python app\main.py`
- Visit: `http://localhost:8000/` → login, then `/dashboard`, `/tickets`, and your new `/reports`.

## Checklist: Add a New Page
- [ ] Create template under `app/web/templates/` (or `templates/admin/`).
- [ ] Add route in `app/web/router.py` (or `admin_router.py`).
- [ ] Protect with `Depends(get_current_user_any)` if needed.
- [ ] Create API(s) under `app/api/` and include router in `main.py`.
- [ ] Fetch and render data in the template.
- [ ] Hook navigation links and verify static assets.

## References
- App setup: `app/main.py`
- Web routes: `app/web/router.py`, `app/web/admin_router.py`
- Middleware: `app/core/middleware.py`
- APIs: `app/api/helpdesk.py`, `app/api/admin.py`, `app/api/integrations.py`
- Services: `app/services/*`
- Repositories: `app/repositories/*`
