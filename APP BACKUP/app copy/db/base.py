from typing import Any
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData


convention = {
    "ix": "ix__%(column_0_label)s",
    "uq": "uq__%(table_name)s__%(column_0_name)s",
    "ck": "ck__%(table_name)s__%(constraint_name)s",
    "fk": "fk__%(table_name)s__%(column_0_name)s__%(referred_table_name)s",
    "pk": "pk__%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with naming convention."""

    metadata = MetaData(naming_convention=convention)