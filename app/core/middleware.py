"""Authentication middleware for automatic redirects."""

import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import verify_jwt_token

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication and automatic redirects."""

    def __init__(self, app, protected_paths: list[str] = None):
        """Initialize the middleware.
        
        Args:
            app: FastAPI application instance.
            protected_paths: List of path prefixes that require authentication.
        """
        super().__init__(app)
        self.protected_paths = protected_paths or ["/admin", "/dashboard"]
        self.public_paths = ["/", "/web/login", "/auth", "/static"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle authentication.
        
        Args:
            request: Incoming request.
            call_next: Next middleware/handler in chain.
            
        Returns:
            Response: Either redirect to login or continue to next handler.
        """
        path = request.url.path
        
        # Skip authentication for public paths
        if any(path.startswith(public_path) for public_path in self.public_paths):
            return await call_next(request)
        
        # Check if path requires authentication
        requires_auth = any(path.startswith(protected_path) for protected_path in self.protected_paths)
        
        if requires_auth:
            # Check for authentication token
            token = None
            
            # Try Authorization header first
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1]
            
            # Fall back to cookie
            if not token:
                token = request.cookies.get("access_token")
            
            # Verify token
            if not token or not verify_jwt_token(token):
                logger.info(f"Unauthenticated access attempt to {path}")
                # Redirect to login page
                return RedirectResponse(url="/", status_code=302)
        
        return await call_next(request)