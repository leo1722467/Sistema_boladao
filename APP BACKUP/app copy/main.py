import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, configure_logging
from app.core.middleware import AuthenticationMiddleware
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.web.router import router as web_router
from app.web.admin_router import router as admin_web_router


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """

    configure_logging()
    app = FastAPI(title="Sistemao Bolado API")
    
    # Add authentication middleware
    app.add_middleware(
        AuthenticationMiddleware,
        protected_paths=["/admin", "/dashboard"]
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(web_router)
    app.include_router(admin_web_router)
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)