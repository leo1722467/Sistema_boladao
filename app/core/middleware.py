"""Authentication & security middlewares."""
import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import verify_jwt_token  # sua função existente

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle authentication and automatic redirects.

    - Para rotas API (prefixos em `api_prefixes`): retorna 401 JSON quando não autenticado.
    - Para rotas Web: redireciona para a página de login.
    """

    def __init__(self, app, protected_paths: list[str] | None = None, api_prefixes: list[str] | None = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/admin", "/dashboard"]
        self.public_paths = [
            "/", "/web/login", "/auth", "/static",
            "/docs", "/redoc", "/openapi.json", "/favicon.ico"
        ]
        # Prefixos considerados API (401 JSON)
        self.api_prefixes = api_prefixes or ["/api"]

    def _is_public(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.public_paths)

    def _is_protected(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.protected_paths) or any(path.startswith(p) for p in self.api_prefixes)

    def _is_api(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.api_prefixes)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip authentication for public paths
        if self._is_public(path):
            return await call_next(request)

        # Only gate protected/api paths
        if not self._is_protected(path):
            return await call_next(request)

        # Extract token (Authorization: Bearer ... OR cookie access_token)
        token = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1] or None
        if not token:
            token = request.cookies.get("access_token")

        is_valid = False
        if token:
            try:
                # sua função pode retornar dict/claims; aqui só conferimos se não levantou erro
                is_valid = bool(verify_jwt_token(token))
            except Exception as exc:  # robustez contra expirado/formato inválido
                logger.info("JWT verification failed: %s", exc, extra={"path": path})
                is_valid = False

        if not is_valid:
            if self._is_api(path):
                # Clientes de API esperam 401 JSON, não redirect.
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            # Para rotas web, mantém o redirect para login
            return RedirectResponse(url="/", status_code=302)

        return await call_next(request)
