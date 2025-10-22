import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import (
    AuthenticationMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.database import initialize_database
from app.core.cache import initialize_cache
from app.core.security_enhanced import SecurityMiddleware, security_monitor, rate_limiter, vulnerability_scanner
from app.api.ops import router as ops_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.helpdesk import router as helpdesk_router
from app.web.router import router as web_router
from app.web.admin_router import router as admin_web_router

settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Setup logging with file output
    import os
    log_path = os.path.join(os.getcwd(), "app-debug.log")
    setup_logging(log_file=log_path)
    # Debug runtime/bcrypt environment to diagnose env mismatches on reload
    import sys, os as _os
    try:
        import bcrypt as _bcrypt
        logging.getLogger(__name__).info(
            "Startup env: exe=%s cwd=%s bcrypt_ver=%s has_hashpw=%s path=%s",
            sys.executable,
            _os.getcwd(),
            getattr(_bcrypt, "__version__", "n/a"),
            hasattr(_bcrypt, "hashpw"),
            getattr(_bcrypt, "__file__", "n/a"),
        )
    except Exception as exc:
        logging.getLogger(__name__).exception("bcrypt import failed: %s", exc)

    app = FastAPI(
        title=settings.APP_NAME,
        description="""
        ## Sistema Boladão - Multi-tenant Helpdesk API

        A comprehensive helpdesk system with inventory management, asset tracking, 
        ticket management, and service order processing.

        ### Features
        - **Multi-tenant architecture** with company-scoped data isolation
        - **Role-based access control** (Admin, Agent, Requester, Viewer)
        - **Inventory management** with automatic asset creation
        - **Asset tracking** with unique serial generation
        - **Ticket management** with status tracking and SLA support
        - **Service order processing** with activity tracking
        - **Comprehensive audit logging** for all operations

        ### Authentication
        All endpoints require JWT authentication. Use `/auth/login` to obtain tokens.

        ### Authorization
        Different endpoints require different permission levels:
        - **Admin**: Full system access
        - **Agent**: Manage tickets, assets, inventory, service orders
        - **Requester**: Create and view own tickets, view assets
        - **Viewer**: Read-only access to assets and tickets

        ### Tenant Scoping
        All data is automatically scoped to the authenticated user's company.
        Users can only access data belonging to their organization.
        """,
        version="2.0.0",
        contact={
            "name": "Sistema Boladão Support",
            "email": "support@sistemaboladao.com",
        },
        license_info={
            "name": "Proprietary",
        },
        openapi_tags=[
            {
                "name": "auth",
                "description": "Authentication and user management operations"
            },
            {
                "name": "helpdesk",
                "description": "Core helpdesk operations: inventory, assets, tickets, service orders"
            },
            {
                "name": "admin",
                "description": "Administrative operations and dynamic CRUD"
            },
            {
                "name": "infra",
                "description": "Infrastructure and health check endpoints"
            }
        ]
    )

    # Global request/response logging and exception capture
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger = logging.getLogger("app.http")
        logger.info("%s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
            logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
            return response
        except Exception:
            logging.getLogger("app.errors").exception("Unhandled exception for %s %s", request.method, request.url.path)
            raise

    # Trusted hosts (ajuste para seu domínio em prod)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    # Request ID + Security headers
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Security hardening (rate limiting, vulnerability scanning)
    app.add_middleware(
        SecurityMiddleware,
        security_monitor=security_monitor,
        rate_limiter=rate_limiter,
        vulnerability_scanner=vulnerability_scanner,
    )

    # Auth middleware
    app.add_middleware(
        AuthenticationMiddleware,
        protected_paths=["/admin", "/dashboard"],
        api_prefixes=["/api", "/admin/api"],
    )

    # CORS
    allowed_origins = settings.CORS_ORIGINS if getattr(settings, "CORS_ORIGINS", None) else ["http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(helpdesk_router)
    app.include_router(web_router)
    app.include_router(admin_web_router)
    app.include_router(ops_router)

    # Static
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

    # Healthcheck
    @app.get("/health", tags=["infra"]) 
    async def health():
        return {"status": "ok", "env": settings.ENV}

    # Startup initializers (migrations, cache)
    @app.on_event("startup")
    async def startup_event():
        await initialize_database()
        await initialize_cache()

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
