from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.modules.auth.service import decode_token


SKIP_AUTH_PATHS = {"/api/auth/register", "/api/auth/login"}

class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件。将 user_id 注入 request.state，register/login 放行。"""

    async def dispatch(self, request: Request, call_next):
        # 放行无需认证的端点
        if request.url.path in SKIP_AUTH_PATHS:
            return await call_next(request)

        # 提取 token (WebSocket 端点的 scope type 不同，跳过)
        if request.scope["type"] != "http":
            return await call_next(request)

        request.state.user_id = None
        request.state.is_admin = False
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload is not None:
                request.state.user_id = payload.get("sub")
                request.state.is_admin = payload.get("is_admin", False)

        return await call_next(request)


def require_admin(request: Request):
    """Raises HTTPException(401) if not authenticated, (403) if not admin."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
