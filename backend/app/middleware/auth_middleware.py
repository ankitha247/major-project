# Lightweight middleware to attach user info to request state.
# Most route-level auth is handled via Depends(get_current_user).
# Use this if you need user context available globally in middleware chain.

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.security import decode_token

UNPROTECTED = {"/health", "/auth/login", "/auth/register", "/docs", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path not in UNPROTECTED:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token:
                payload = decode_token(token)
                request.state.user = payload
            else:
                request.state.user = None
        return await call_next(request)