from typing import Optional
import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth import AuthService
from app.core.config import get_settings
from app.api.auth import get_current_user_any

logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/web/templates")
settings = get_settings()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render home page that redirects to login."""

    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/web/login")
async def login_form(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """Process login form and redirect to dashboard.

    Args:
        request: Request object.
        form_data: OAuth2 password form data.
        session: DB session.

    Returns:
        RedirectResponse to dashboard on success.
    """

    svc = AuthService()
    try:
        access, _, _ = await svc.authenticate(session, email=form_data.username, password=form_data.password)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=False,
        max_age=settings.ACCESS_EXPIRES_MIN * 60,
        path="/",
        samesite="lax",
        secure=False,
    )
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render dashboard page after login."""

    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/web/tables", response_class=HTMLResponse)
async def tables(request: Request, _: object = Depends(get_current_user_any)) -> HTMLResponse:
    """Render page listing all tables with navigation links.

    Args:
        request: FastAPI request object.

    Returns:
        HTMLResponse with tables page.
    """

    return templates.TemplateResponse("tables.html", {"request": request})


@router.get("/assets", response_class=HTMLResponse)
async def assets_page(request: Request) -> HTMLResponse:
    """Render asset management page."""
    return templates.TemplateResponse("assets.html", {"request": request})


@router.get("/tickets", response_class=HTMLResponse)
async def tickets_page(request: Request) -> HTMLResponse:
    """Render ticket management page."""
    return templates.TemplateResponse("tickets.html", {"request": request})


@router.get("/service-orders", response_class=HTMLResponse)
async def service_orders_page(request: Request) -> HTMLResponse:
    """Render service order management page."""
    return templates.TemplateResponse("service_orders.html", {"request": request})


@router.get("/integrations", response_class=HTMLResponse)
async def integrations_page(request: Request) -> HTMLResponse:
    """Render integrations management page."""
    return templates.TemplateResponse("integrations.html", {"request": request})


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request) -> HTMLResponse:
    """Render inventory management page."""
    return templates.TemplateResponse("inventory.html", {"request": request})


@router.get("/web/logout")
async def logout() -> RedirectResponse:
    """Clear auth cookie and redirect to home.

    Returns:
        RedirectResponse: Redirect to login page after clearing cookie.
    """

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", path="/")
    return response
@router.get("/tickets/new", response_class=HTMLResponse)
async def ticket_create_page(request: Request) -> HTMLResponse:
    """Render new ticket creation page."""
    return templates.TemplateResponse("ticket_create.html", {"request": request})