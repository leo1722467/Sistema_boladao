"""
Bootstrap full schema using SQLAlchemy metadata.

Revision ID: 000000000001
Revises: 8e4d4b57efe1
Create Date: 2025-10-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000000000001"
down_revision = "8e4d4b57efe1"
branch_labels = None
depends_on = None


def upgrade():
    """Create all tables defined in SQLAlchemy metadata."""
    from app.db.base import Base
    from app.db import models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    """Drop all tables defined in SQLAlchemy metadata."""
    from app.db.base import Base
    from app.db import models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)