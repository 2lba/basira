from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class CORSAlwaysOnMiddleware(BaseHTTPMiddleware):
    """CORS that survives exception responses (e.g. 500s from inner middleware).

    Wraps starlette's CORSMiddleware but always attaches headers even when the
    downstream app raises before CORS middleware would normally inject them.
    """

    def __init__(self, app: ASGIApp, allow_origins: list[str]):
        super().__init__(app)
        self._allow_origins = allow_origins
        self._allow_set = set(allow_origins)

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        try:
            response = await call_next(request)
        except Exception:
            # log the traceback before swallowing - otherwise debugging 500s
            # routed through this middleware is impossible.
            from app.core.logging import get_logger

            get_logger("basira.middleware").exception(
                "middleware.unhandled",
                path=str(request.url.path),
                method=request.method,
            )
            response = Response(
                content='{"error":{"code":"INTERNAL","message":"internal server error"}}',
                status_code=500,
                media_type="application/json",
            )
            self._apply(response, origin)
            return response

        self._apply(response, origin)
        return response

    def _apply(self, response: Response, origin: str | None) -> None:
        if origin and origin in self._allow_set:
            response.headers["access-control-allow-origin"] = origin
            response.headers["access-control-allow-credentials"] = "true"
            response.headers["vary"] = "origin"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "no-referrer")
        response.headers.setdefault(
            "permissions-policy",
            "accelerometer=(), camera=(), geolocation=(), microphone=()",
        )
        return response


def cors_preflight_middleware(allow_origins: list[str]) -> CORSMiddleware:
    return CORSMiddleware(
        app=None,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
