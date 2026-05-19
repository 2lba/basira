from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.repos import router as repos_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.scans import router as scans_router
from app.api.routes.webhooks import router as webhook_router
from app.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CORSAlwaysOnMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter

setup_logging()
log = get_logger("reviewly.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api.startup", env=settings.app_env, version=__version__)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="reviewly",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(CORSAlwaysOnMiddleware, allow_origins=settings.cors_origin_list)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(RateLimitExceeded, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(webhook_router)
    app.include_router(repos_router)
    app.include_router(reviews_router)
    app.include_router(scans_router)

    if settings.e2e_test_mode:
        from app.api.routes.e2e import router as e2e_router

        app.include_router(e2e_router)
        log.warning("e2e_test_mode enabled; /test/* routes mounted")

    return app


app = create_app()


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "reviewly", "version": __version__}
