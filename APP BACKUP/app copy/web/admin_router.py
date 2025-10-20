import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.api.auth import get_current_user_any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-web"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/{model}", response_class=HTMLResponse)
async def admin_model_list(model: str, request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    """Render list page for a model."""

    return templates.TemplateResponse("admin/model_list.html", {"request": request, "model": model})


@router.get("/{model}/create", response_class=HTMLResponse)
async def admin_model_create(model: str, request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    """Render create form for a model."""

    return templates.TemplateResponse("admin/model_create.html", {"request": request, "model": model})


@router.get("/{model}/{item_id}", response_class=HTMLResponse)
async def admin_model_edit(model: str, item_id: int, request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    """Render edit form for a model item."""

    return templates.TemplateResponse("admin/model_edit.html", {"request": request, "model": model, "item_id": item_id})