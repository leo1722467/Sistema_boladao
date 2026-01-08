import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.api.auth import get_current_user_any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-web"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/flow-engine", response_class=HTMLResponse)
async def flow_engine(request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    """Render dynamic flow engine configuration page."""

    return templates.TemplateResponse("admin/flow_engine.html", {"request": request})


@router.get("/models")
async def get_models(_: Any = Depends(get_current_user_any)):
    """Get list of available models"""
    import inspect
    from app.db import models
    
    # Get all SQLAlchemy model classes
    model_classes = []
    for name, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and hasattr(obj, '__tablename__'):
            model_classes.append(name)
    
    return model_classes


@router.get("/{model}/schema")
async def get_model_schema(model: str, _: Any = Depends(get_current_user_any)):
    """Get schema information for a specific model"""
    import inspect
    from app.db import models
    from sqlalchemy import inspect as sqlalchemy_inspect
    
    # Find the model class
    model_class = None
    for name, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and hasattr(obj, '__tablename__') and name.lower() == model.lower():
            model_class = obj
            break
    
    if not model_class:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get column information
    inspector = sqlalchemy_inspect(model_class)
    columns = []
    
    for column in inspector.columns:
        columns.append({
            "name": column.name,
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "foreign_key": len(column.foreign_keys) > 0
        })
    
    return {
        "model": model,
        "table_name": model_class.__tablename__,
        "columns": columns
    }

@router.get("/dynamic-flow")
async def dynamic_flow(request: Request, model: str, _: Any = Depends(get_current_user_any)):
    """Dynamic flow interface for any model"""
    return templates.TemplateResponse("admin/dynamic_flow.html", {
        "request": request,
        "model_name": model
    })


@router.get("/chamado/create-flow", response_class=HTMLResponse)
async def chamado_create_flow(request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    """Render step-by-step Chamado creation flow."""

    return templates.TemplateResponse("admin/chamado_create_flow.html", {"request": request})

@router.get("/helpdesk", response_class=HTMLResponse)
async def admin_helpdesk(request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    return templates.TemplateResponse("admin_helpdesk.html", {"request": request})

@router.get("/kb", response_class=HTMLResponse)
async def admin_kb(request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    return templates.TemplateResponse("admin_kb.html", {"request": request})

@router.get("/notifications", response_class=HTMLResponse)
async def admin_notifications(request: Request, _: Any = Depends(get_current_user_any)) -> HTMLResponse:
    return templates.TemplateResponse("admin_notifications.html", {"request": request})


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
