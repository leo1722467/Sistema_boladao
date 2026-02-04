"""
Database management utilities for migrations, schema versioning, and operations.
Provides tools for database initialization, migration management, and health checks.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text, inspect
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database management utility for migrations and operations.
    Handles schema versioning, migration execution, and database health checks.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.alembic_cfg = Config("alembic.ini")
        self.alembic_cfg.set_main_option("sqlalchemy.url", str(self.settings.DB_URL))
    
    async def get_current_revision(self) -> Optional[str]:
        """Get the current database revision."""
        try:
            engine = create_async_engine(str(self.settings.DB_URL))
            
            async with engine.connect() as connection:
                # Check if alembic_version table exists
                result = await connection.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                ))
                
                if not result.fetchone():
                    return None
                
                # Get current revision
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Error getting current revision: {e}")
            return None
    
    async def get_available_revisions(self) -> List[str]:
        """Get list of available migration revisions."""
        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            revisions = []
            
            for revision in script_dir.walk_revisions():
                revisions.append(revision.revision)
            
            return list(reversed(revisions))  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Error getting available revisions: {e}")
            return []
    
    async def check_migration_status(self) -> Dict[str, Any]:
        """Check the current migration status."""
        current_revision = await self.get_current_revision()
        available_revisions = await self.get_available_revisions()
        
        if not current_revision:
            status = "not_initialized"
            pending_migrations = available_revisions
        elif current_revision == available_revisions[-1] if available_revisions else None:
            status = "up_to_date"
            pending_migrations = []
        else:
            status = "pending_migrations"
            try:
                current_index = available_revisions.index(current_revision)
                pending_migrations = available_revisions[current_index + 1:]
            except ValueError:
                pending_migrations = available_revisions
        
        return {
            "status": status,
            "current_revision": current_revision,
            "latest_revision": available_revisions[-1] if available_revisions else None,
            "pending_migrations": pending_migrations,
            "total_revisions": len(available_revisions)
        }
    
    def run_migrations(self, target_revision: Optional[str] = None) -> bool:
        """Run migrations synchronously. Prefer `run_migrations_async` inside async contexts."""
        try:
            rev = target_revision or "heads"
            command.upgrade(self.alembic_cfg, rev)
            logger.info(f"Successfully ran migrations to {target_revision or 'head'}")
            return True
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return False

    async def run_migrations_async(self, target_revision: Optional[str] = None) -> bool:
        """Run Alembic migrations from an async context without event-loop conflicts."""
        try:
            rev = target_revision or "heads"
            await asyncio.to_thread(command.upgrade, self.alembic_cfg, rev)
            logger.info(f"Successfully ran migrations to {target_revision or 'head'} (async)")
            return True
        except Exception as e:
            logger.error(f"Error running migrations (async): {e}")
            return False
    
    def create_migration(self, message: str, auto_generate: bool = True) -> bool:
        """Create a new migration."""
        try:
            if auto_generate:
                command.revision(self.alembic_cfg, message=message, autogenerate=True)
            else:
                command.revision(self.alembic_cfg, message=message)
            
            logger.info(f"Successfully created migration: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating migration: {e}")
            return False
    
    def rollback_migration(self, target_revision: str) -> bool:
        """Rollback to a specific migration."""
        try:
            command.downgrade(self.alembic_cfg, target_revision)
            logger.info(f"Successfully rolled back to revision: {target_revision}")
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back migration: {e}")
            return False
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Perform comprehensive database health check."""
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            engine = create_async_engine(str(self.settings.DB_URL))
            
            # Test basic connectivity
            async with engine.connect() as connection:
                start_time = datetime.utcnow()
                await connection.execute(text("SELECT 1"))
                end_time = datetime.utcnow()
                
                health_status["checks"]["connectivity"] = {
                    "status": "pass",
                    "response_time_ms": int((end_time - start_time).total_seconds() * 1000)
                }
            
            # Check migration status
            migration_status = await self.check_migration_status()
            health_status["checks"]["migrations"] = {
                "status": "pass" if migration_status["status"] == "up_to_date" else "warn",
                "current_revision": migration_status["current_revision"],
                "pending_migrations": len(migration_status["pending_migrations"])
            }
            
            # Check table existence
            async with engine.connect() as connection:
                inspector = inspect(connection.sync_connection)
                tables = inspector.get_table_names()
                
                expected_tables = [
                    "empresa", "contato", "user_auth", "ativo", "estoque",
                    "chamado", "ordem_servico", "outbox_events", "webhook_endpoints"
                ]
                
                missing_tables = [table for table in expected_tables if table not in tables]
                
                health_status["checks"]["schema"] = {
                    "status": "pass" if not missing_tables else "fail",
                    "total_tables": len(tables),
                    "missing_tables": missing_tables
                }
            
            # Check database size (for SQLite)
            if "sqlite" in str(self.settings.DB_URL):
                import os
                db_path = str(self.settings.DB_URL).replace("sqlite+aiosqlite:///", "")
                if os.path.exists(db_path):
                    db_size = os.path.getsize(db_path)
                    health_status["checks"]["storage"] = {
                        "status": "pass",
                        "size_bytes": db_size,
                        "size_mb": round(db_size / (1024 * 1024), 2)
                    }
            
            # Overall status
            failed_checks = [check for check in health_status["checks"].values() if check["status"] == "fail"]
            if failed_checks:
                health_status["status"] = "unhealthy"
            elif any(check["status"] == "warn" for check in health_status["checks"].values()):
                health_status["status"] = "degraded"
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status

    async def ensure_schema_consistency(self) -> None:
        """Ensure critical columns and indexes exist; apply lightweight fixes for SQLite."""
        engine = create_async_engine(str(self.settings.DB_URL))
        async with engine.begin() as conn:
            # ativo.empresa_id column
            try:
                result = await conn.execute(text("PRAGMA table_info('ativo')"))
                cols = [row[1] for row in result.fetchall()]  # row[1] is column name
                if 'empresa_id' not in cols:
                    await conn.execute(text("ALTER TABLE ativo ADD COLUMN empresa_id INTEGER"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ativo_empresa_id ON ativo(empresa_id)"))
            except Exception as e:
                logger.error(f"Failed to ensure ativo.empresa_id: {e}")
            
            # estoque.empresa_id column
            try:
                result = await conn.execute(text("PRAGMA table_info('estoque')"))
                cols = [row[1] for row in result.fetchall()]
                if 'empresa_id' not in cols:
                    await conn.execute(text("ALTER TABLE estoque ADD COLUMN empresa_id INTEGER"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_estoque_empresa_id ON estoque(empresa_id)"))
            except Exception as e:
                logger.error(f"Failed to ensure estoque.empresa_id: {e}")
            
            # pendencia table
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='pendencia'"))
                exists = bool(result.fetchone())
                if not exists:
                    await conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS pendencia (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tag TEXT,
                            os_origem_id INTEGER,
                            descricao TEXT,
                            status TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            closed_at DATETIME,
                            FOREIGN KEY(os_origem_id) REFERENCES ordem_servico(id)
                        )
                    """))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pendencia_status ON pendencia(status)"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pendencia_os ON pendencia(os_origem_id)"))
            except Exception as e:
                logger.error(f"Failed to ensure pendencia table: {e}")
            
            # ordem_servico_pendencia_solucao junction
            try:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='ordem_servico_pendencia_solucao'"))
                exists = bool(result.fetchone())
                if not exists:
                    await conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS ordem_servico_pendencia_solucao (
                            ordem_servico_id INTEGER NOT NULL,
                            pendencia_id INTEGER NOT NULL,
                            PRIMARY KEY(ordem_servico_id, pendencia_id),
                            FOREIGN KEY(ordem_servico_id) REFERENCES ordem_servico(id) ON DELETE CASCADE,
                            FOREIGN KEY(pendencia_id) REFERENCES pendencia(id) ON DELETE CASCADE
                        )
                    """))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_os_pendencia_solucao_os ON ordem_servico_pendencia_solucao(ordem_servico_id)"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_os_pendencia_solucao_p ON ordem_servico_pendencia_solucao(pendencia_id)"))
            except Exception as e:
                logger.error(f"Failed to ensure ordem_servico_pendencia_solucao table: {e}")
        await engine.dispose()
    
    async def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Create a database backup (SQLite only)."""
        if "sqlite" not in str(self.settings.DB_URL):
            logger.warning("Database backup only supported for SQLite")
            return False
        
        try:
            import shutil
            from datetime import datetime
            
            source_path = str(self.settings.DB_URL).replace("sqlite+aiosqlite:///", "")
            
            if not backup_path:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                backup_path = f"backup_{timestamp}.db"
            
            shutil.copy2(source_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return False
    
    async def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup (SQLite only)."""
        if "sqlite" not in str(self.settings.DB_URL):
            logger.warning("Database restore only supported for SQLite")
            return False
        
        try:
            import shutil
            import os
            
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            target_path = str(self.settings.DB_URL).replace("sqlite+aiosqlite:///", "")
            
            # Create backup of current database
            current_backup = f"current_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
            if os.path.exists(target_path):
                shutil.copy2(target_path, current_backup)
                logger.info(f"Current database backed up to: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, target_path)
            logger.info(f"Database restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            return False
    
    async def optimize_database(self) -> bool:
        """Optimize database performance (SQLite VACUUM)."""
        try:
            engine = create_async_engine(str(self.settings.DB_URL))
            
            async with engine.connect() as connection:
                await connection.execute(text("VACUUM"))
                await connection.execute(text("ANALYZE"))
            
            logger.info("Database optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return False
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics and metrics."""
        try:
            engine = create_async_engine(str(self.settings.DB_URL))
            stats = {}
            
            async with engine.connect() as connection:
                # Get table row counts
                inspector = inspect(connection.sync_connection)
                tables = inspector.get_table_names()
                
                table_stats = {}
                for table in tables:
                    try:
                        result = await connection.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        table_stats[table] = count
                    except Exception:
                        table_stats[table] = 0
                
                stats["table_counts"] = table_stats
                stats["total_records"] = sum(table_stats.values())
                
                # Get database info (SQLite specific)
                if "sqlite" in str(self.settings.DB_URL):
                    result = await connection.execute(text("PRAGMA database_list"))
                    db_info = result.fetchall()
                    stats["database_info"] = [dict(row._mapping) for row in db_info]
                    
                    result = await connection.execute(text("PRAGMA page_count"))
                    page_count = result.scalar()
                    
                    result = await connection.execute(text("PRAGMA page_size"))
                    page_size = result.scalar()
                    
                    stats["storage"] = {
                        "page_count": page_count,
                        "page_size": page_size,
                        "estimated_size_bytes": page_count * page_size
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {}


# Global database manager instance
db_manager = DatabaseManager()


async def initialize_database():
    """Initialize database with migrations."""
    logger.info("Initializing database...")
    # Always run migrations to ensure schema is in sync, handling multi-head branches
    logger.info("Running database migrations...")
    success = await db_manager.run_migrations_async()
    
    if success:
        logger.info("Database migrations completed successfully")
    else:
        logger.error("Database migrations failed")
        raise RuntimeError("Failed to run database migrations")

    # Post-migration schema consistency checks and repairs
    try:
        await db_manager.ensure_schema_consistency()
        logger.info("Schema consistency ensured")
    except Exception as e:
        logger.error(f"Schema consistency check failed: {e}")


async def check_database_ready() -> bool:
    """Check if database is ready for use."""
    try:
        health = await db_manager.check_database_health()
        return health["status"] in ["healthy", "degraded"]
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        return False
