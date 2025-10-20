import logging
import inspect
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, ForeignKey, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.db.base import Base
from app.db import models as db_models
from app.api.auth import get_current_user_any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _model_map() -> Dict[str, Type[Base]]:
    """Return a mapping of model name to SQLAlchemy ORM class.

    Returns:
        Dict[str, Type[Base]]: Mapping of class name to model class.
    """

    mapping: Dict[str, Type[Base]] = {}
    for name, obj in inspect.getmembers(db_models):
        if inspect.isclass(obj) and issubclass(obj, Base) and hasattr(obj, "__tablename__"):
            mapping[name] = obj
    return mapping


def _get_model(name: str) -> Type[Base]:
    """Get model class by name.

    Args:
        name: Class name string (case-insensitive).

    Returns:
        SQLAlchemy ORM class.

    Raises:
        HTTPException: If model name is invalid.
    """

    mapping = _model_map()
    
    # First try exact match
    model = mapping.get(name)
    if model:
        return model
    
    # Try case-insensitive match
    for model_name, model_class in mapping.items():
        if model_name.lower() == name.lower():
            return model_class
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model: {name}")


def _model_columns(model: Type[Base]) -> List[str]:
    """Return list of column names for a model (excluding relationships)."""

    return [c.name for c in model.__table__.columns]


def _get_column_to_attr_mapping(model: Type[Base]) -> Dict[str, str]:
    """Get mapping from database column names to Python attribute names."""
    
    mapping = {}
    for column in model.__table__.columns:
        # Find the corresponding attribute name in the model
        attr_name = None
        for attr in dir(model):
            if hasattr(model, attr):
                attr_obj = getattr(model, attr)
                if hasattr(attr_obj, 'property') and hasattr(attr_obj.property, 'columns'):
                    if attr_obj.property.columns and attr_obj.property.columns[0] is column:
                        attr_name = attr
                        break
        
        # Fallback to column name if no mapped attribute found
        if attr_name is None:
            attr_name = column.name
            
        mapping[column.name] = attr_name
    
    return mapping


def _pk_column(model: Type[Base]) -> str:
    """Return primary key column name."""

    for col in model.__table__.columns:
        if col.primary_key:
            return col.name
    return "id"


def _to_dict(instance: Base) -> Dict[str, Any]:
    """Serialize an ORM instance to a dictionary of its columns."""

    model = instance.__class__
    result = {}
    
    # Use the actual mapped attributes instead of database column names
    for column in model.__table__.columns:
        # Find the corresponding attribute name in the model
        attr_name = None
        for attr in dir(model):
            if hasattr(model, attr):
                attr_obj = getattr(model, attr)
                if hasattr(attr_obj, 'property') and hasattr(attr_obj.property, 'columns'):
                    if attr_obj.property.columns and attr_obj.property.columns[0] is column:
                        attr_name = attr
                        break
        
        # Fallback to column name if no mapped attribute found
        if attr_name is None:
            attr_name = column.name
            
        # Only include if the attribute actually exists on the instance
        if hasattr(instance, attr_name):
            value = getattr(instance, attr_name)
            
            # Convert datetime objects to ISO format strings for JSON serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            
            result[column.name] = value
    
    return result


def _get_foreign_keys(model: Type[Base]) -> Dict[str, Dict[str, Any]]:
    """Get foreign key information for a model."""
    
    foreign_keys = {}
    for col in model.__table__.columns:
        if col.foreign_keys:
            fk = list(col.foreign_keys)[0]  # Get first foreign key
            target_table = fk.column.table.name
            target_column = fk.column.name
            
            # Try to find the target model class
            target_model_name = None
            for name, model_class in _model_map().items():
                if hasattr(model_class, '__tablename__') and model_class.__tablename__ == target_table:
                    target_model_name = name
                    break
            
            foreign_keys[col.name] = {
                "target_table": target_table,
                "target_column": target_column,
                "target_model": target_model_name
            }
    
    return foreign_keys


def _get_display_field(model: Type[Base]) -> str:
    """Get the best field to display for a model in dropdowns."""
    
    # Common display field names in order of preference
    display_fields = ['nome', 'name', 'titulo', 'title', 'descricao', 'description', 'numero', 'number']
    
    model_columns = [c.name for c in model.__table__.columns]
    
    for field in display_fields:
        if field in model_columns:
            return field
    
    # If no common display field found, use the first non-id column
    for col in model.__table__.columns:
        if not col.primary_key and col.name not in ['criado_em', 'atualizado_em', 'created_at', 'updated_at']:
            return col.name
    
    # Fallback to primary key
    return _pk_column(model)


def _get_datetime_columns(model: Type[Base]) -> List[str]:
    """Get list of datetime column names for a model."""
    
    datetime_columns = []
    for column in model.__table__.columns:
        if isinstance(column.type, DateTime):
            datetime_columns.append(column.name)
    return datetime_columns


def _convert_datetime_values(model: Type[Base], data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert string datetime values to Python datetime objects."""
    
    datetime_columns = _get_datetime_columns(model)
    converted_data = data.copy()
    
    logger.info(f"Model: {model.__name__}, Datetime columns: {datetime_columns}")
    logger.info(f"Incoming data: {data}")
    
    for key, value in data.items():
        if key in datetime_columns:
            logger.info(f"Processing datetime field {key} with value: {value} (type: {type(value)})")
            
            # Handle empty strings and None values
            if value is None or (isinstance(value, str) and value.strip() == ''):
                converted_data[key] = None
                logger.info(f"Converted empty/null {key} to None")
                continue
                
            if isinstance(value, str):
                try:
                    # Try multiple datetime formats
                    if 'T' in value:
                        # ISO format with T separator
                        converted_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif ' ' in value:
                        # Format with space separator (YYYY-MM-DD HH:MM:SS)
                        converted_data[key] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Date only format (YYYY-MM-DD)
                        converted_data[key] = datetime.strptime(value, '%Y-%m-%d')
                    
                    logger.info(f"Successfully converted {key}: {value} -> {converted_data[key]}")
                except ValueError as e:
                    # If parsing fails, convert to None for nullable fields
                    logger.error(f"Failed to parse datetime value for {key}: {value}, error: {e}, setting to None")
                    converted_data[key] = None
            elif isinstance(value, (int, float)):
                # Handle timestamp values
                try:
                    converted_data[key] = datetime.fromtimestamp(value)
                    logger.info(f"Converted timestamp {key}: {value} -> {converted_data[key]}")
                except (ValueError, OSError) as e:
                    logger.error(f"Failed to convert timestamp for {key}: {value}, error: {e}, setting to None")
                    converted_data[key] = None
    
    return converted_data


@router.get("/{model}/schema")
async def model_schema(model: str, _: Any = Depends(get_current_user_any)) -> Dict[str, Any]:
    """Return basic schema info for a model.

    Args:
        model: Model class name.

    Returns:
        Dict with primary key name, list of columns with types, and foreign key info.
    """

    m = _get_model(model)
    pk = _pk_column(m)
    foreign_keys = _get_foreign_keys(m)
    
    cols: List[Dict[str, Any]] = []
    for col in m.__table__.columns:
        col_info = {
            "name": col.name,
            "type": col.type.__class__.__name__,
            "primary_key": bool(col.primary_key),
            "nullable": bool(col.nullable),
            "server_default": bool(col.server_default),
            "is_foreign_key": col.name in foreign_keys
        }
        
        # Add foreign key info if this column is a foreign key
        if col.name in foreign_keys:
            col_info["foreign_key"] = foreign_keys[col.name]
        
        cols.append(col_info)
    
    return {
        "model": model, 
        "primary_key": pk, 
        "columns": cols,
        "foreign_keys": foreign_keys
    }


@router.get("/{model}/foreign-key-options/{field}")
async def get_foreign_key_options(
    model: str, 
    field: str, 
    session: AsyncSession = Depends(get_db),
    _: Any = Depends(get_current_user_any)
) -> List[Dict[str, Any]]:
    """Get foreign key options for a specific field.

    Args:
        model: Source model class name.
        field: Foreign key field name.
        session: DB session.

    Returns:
        List of {id, display} dicts for dropdown options.
    """

    try:
        m = _get_model(model)
        foreign_keys = _get_foreign_keys(m)
        
        if field not in foreign_keys:
            logger.warning(f"Field {field} is not a foreign key in model {model}. Available foreign keys: {list(foreign_keys.keys())}")
            # Return empty list instead of raising an error to prevent UI breakage
            return []
        
        target_model_name = foreign_keys[field]["target_model"]
        if not target_model_name:
            logger.warning(f"Could not find target model for foreign key {field} in model {model}")
            return []
        
        target_model = _get_model(target_model_name)
        display_field = _get_display_field(target_model)
        pk_field = _pk_column(target_model)
        
        # Fetch all records from target model
        res = await session.execute(select(target_model).limit(1000))
        records = res.scalars().all()
        
        options = []
        for record in records:
            pk_value = getattr(record, pk_field)
            display_value = getattr(record, display_field, str(pk_value))
            options.append({"id": pk_value, "display": str(display_value)})
        
        return options
        
    except Exception as e:
        logger.error(f"Error loading foreign key options for {model}.{field}: {str(e)}")
        # Return empty list instead of raising an error to prevent UI breakage
        return []


@router.get("/models")
async def list_models(_: Any = Depends(get_current_user_any)) -> List[str]:
    """List available ORM model names."""

    return sorted(_model_map().keys())


@router.get("/{model}/items")
async def list_items(model: str, session: AsyncSession = Depends(get_db), _: Any = Depends(get_current_user_any)) -> List[Dict[str, Any]]:
    """List items for a model.

    Args:
        model: Model class name.
        session: DB session.

    Returns:
        List of item dicts.
    """

    m = _get_model(model)
    res = await session.execute(select(m).limit(100))
    items = [
        _to_dict(obj)
        for obj in res.scalars().all()
    ]
    return items


@router.get("/{model}/items/{item_id}")
async def get_item(model: str, item_id: int, session: AsyncSession = Depends(get_db), _: Any = Depends(get_current_user_any)) -> Dict[str, Any]:
    """Get a single item by primary key."""

    m = _get_model(model)
    obj = await session.get(m, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _to_dict(obj)


@router.post("/{model}/items")
async def create_item(model: str, payload: Dict[str, Any], session: AsyncSession = Depends(get_db), _: Any = Depends(get_current_user_any)) -> Dict[str, Any]:
    """Create a new item for a model.

    Args:
        model: Model class name.
        payload: JSON body with column values.

    Returns:
        Created item as dict.
    """

    m = _get_model(model)
    cols = set(_model_columns(m))
    pk = _pk_column(m)
    column_to_attr = _get_column_to_attr_mapping(m)
    
    # Convert datetime values first
    converted_payload = _convert_datetime_values(m, payload)
    
    # Filter payload to only include valid columns and map to attribute names
    data = {}
    for k, v in converted_payload.items():
        if k in cols and k != pk:
            attr_name = column_to_attr.get(k, k)
            data[attr_name] = v
    
    obj = m(**data)
    session.add(obj)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.orig))
    await session.refresh(obj)
    return _to_dict(obj)


@router.put("/{model}/items/{item_id}")
async def update_item(model: str, item_id: int, payload: Dict[str, Any], session: AsyncSession = Depends(get_db), _: Any = Depends(get_current_user_any)) -> Dict[str, Any]:
    """Update an item by primary key."""

    m = _get_model(model)
    obj = await session.get(m, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    cols = set(_model_columns(m))
    pk = _pk_column(m)
    column_to_attr = _get_column_to_attr_mapping(m)
    
    # Convert datetime values first
    converted_payload = _convert_datetime_values(m, payload)
    
    for k, v in converted_payload.items():
        if k in cols and k != pk:
            attr_name = column_to_attr.get(k, k)
            setattr(obj, attr_name, v)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.orig))
    await session.refresh(obj)
    return _to_dict(obj)


@router.delete("/{model}/items/{item_id}")
async def delete_item(model: str, item_id: int, session: AsyncSession = Depends(get_db), _: Any = Depends(get_current_user_any)) -> Dict[str, Any]:
    """Delete an item by primary key."""

    m = _get_model(model)
    obj = await session.get(m, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(obj)
    await session.commit()
    return {"status": "deleted", "model": model, "id": item_id}