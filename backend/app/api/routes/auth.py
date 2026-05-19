from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth_deps import (
    ACCESS_COOKIE,
    CSRF_STATE_COOKIE,
    POST_LOGIN_REDIRECT_COOKIE,
    REFRESH_COOKIE,
    current_user,
)
from app.core.crypto import (
    CryptoError,
    constant_time_eq,
    generate_csrf_state,
    issue_access_token,
)
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.integrations.github_oauth import (
    GithubOAuthError,
    authorize_url,
    exchange_code,
    fetch_profile,
)
from app.models.user import User
from app.schemas.auth import LoginUrlResponse, MeResponse
from app.services.auth_service import (
    AuthError,
    clear_failures,
    is_locked_out,
    issue_refresh,
    record_failure,
    revoke_refresh,
    rotate_refresh,
    upsert_user_from_github,
)

log = get_logger("reviewly.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_kwargs(secure_override: bool | None = None) -> dict:
    s = get_settings()
    secure = secure_override if secure_override is not None else s.is_production
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }


def _set_session_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=s.jwt_access_ttl_minutes * 60,
        **_cookie_kwargs(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=s.jwt_refresh_ttl_days * 86400,
        **_cookie_kwargs(),
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _safe_redirect(target: str | None) -> str:
    s = get_settings()
    fallback = s.frontend_base_url
    if not target:
        return fallback
    try:
        u = urlparse(target)
    except ValueError:
        return fallback
    fe = urlparse(s.frontend_base_url)
    if u.netloc and (u.scheme, u.netloc) != (fe.scheme, fe.netloc):
        return fallback
    return target if target.startswith("/") or target.startswith(s.frontend_base_url) else fallback


def _redirect_uri() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/auth/github/callback"


@router.get("/github/login")
@limiter.limit(get_settings().rate_limit_auth)
async def github_login(
    request: Request,
    next: str | None = Query(default=None, max_length=512),
):
    state = generate_csrf_state()
    try:
        url = authorize_url(_redirect_uri(), state)
    except GithubOAuthError as e:
        raise AppError("GITHUB_NOT_CONFIGURED", str(e), status.HTTP_503_SERVICE_UNAVAILABLE) from e

    resp = RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(CSRF_STATE_COOKIE, state, max_age=600, **_cookie_kwargs())
    if next:
        resp.set_cookie(POST_LOGIN_REDIRECT_COOKIE, next[:512], max_age=600, **_cookie_kwargs())
    return resp


@router.get("/github/login-url", response_model=LoginUrlResponse)
@limiter.limit(get_settings().rate_limit_auth)
async def github_login_url(request: Request):
    state = generate_csrf_state()
    try:
        url = authorize_url(_redirect_uri(), state)
    except GithubOAuthError as e:
        raise AppError("GITHUB_NOT_CONFIGURED", str(e), status.HTTP_503_SERVICE_UNAVAILABLE) from e
    return LoginUrlResponse(url=url)


@router.get("/github/callback")
@limiter.limit(get_settings().rate_limit_auth)
async def github_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    state_cookie: str | None = Cookie(default=None, alias=CSRF_STATE_COOKIE),
    next_cookie: str | None = Cookie(default=None, alias=POST_LOGIN_REDIRECT_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise AppError(
            "OAUTH_DENIED",
            error_description or error,
            status.HTTP_400_BAD_REQUEST,
        )
    if not code or not state:
        raise AppError("OAUTH_BAD_REQUEST", "missing code or state", status.HTTP_400_BAD_REQUEST)
    if not state_cookie or not constant_time_eq(state, state_cookie):
        raise AppError("OAUTH_STATE_MISMATCH", "state mismatch", status.HTTP_400_BAD_REQUEST)

    ip = request.client.host if request.client else None
    if ip and await is_locked_out("oauth", ip):
        raise AppError(
            "RATE_LIMITED",
            "too many failed login attempts; try again later",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        access_token = await exchange_code(code, _redirect_uri())
        profile = await fetch_profile(access_token)
    except GithubOAuthError as e:
        if ip:
            await record_failure("oauth", ip)
        log.warning("oauth.exchange_failed", err=str(e))
        raise AppError(
            "OAUTH_FAILED", "github authorization failed", status.HTTP_400_BAD_REQUEST
        ) from e

    try:
        user = await upsert_user_from_github(db, profile, access_token)
    except AuthError as e:
        raise AppError(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE) from e

    if ip:
        await clear_failures("oauth", ip)

    try:
        access = issue_access_token(str(user.id), {"login": user.github_login})
    except CryptoError as e:
        raise AppError("CRYPTO_NOT_CONFIGURED", str(e), status.HTTP_503_SERVICE_UNAVAILABLE) from e

    refresh_token, _ = await issue_refresh(
        db,
        user.id,
        request.headers.get("user-agent"),
        ip,
    )

    log.info("auth.login", user_id=str(user.id), login=user.github_login)

    target = _safe_redirect(next_cookie)
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    _set_session_cookies(resp, access, refresh_token)
    resp.delete_cookie(CSRF_STATE_COOKIE, path="/")
    resp.delete_cookie(POST_LOGIN_REDIRECT_COOKIE, path="/")
    return resp


@router.post("/refresh")
@limiter.limit(get_settings().rate_limit_auth)
async def refresh(
    request: Request,
    response: Response,
    refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if not refresh:
        raise AppError("NOT_AUTHENTICATED", "no refresh token", status.HTTP_401_UNAUTHORIZED)
    try:
        user, new_refresh = await rotate_refresh(
            db,
            refresh,
            request.headers.get("user-agent"),
            request.client.host if request.client else None,
        )
    except AuthError as e:
        _clear_session_cookies(response)
        raise AppError(e.code, e.message, status.HTTP_401_UNAUTHORIZED) from e

    access = issue_access_token(str(user.id), {"login": user.github_login})
    _set_session_cookies(response, access, new_refresh)
    return {"ok": True}


@router.post("/logout")
async def logout(
    response: Response,
    refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if refresh:
        await revoke_refresh(db, refresh)
    _clear_session_cookies(response)
    return {"ok": True}


def _install_url() -> str:
    name = get_settings().github_app_name or "reviewly"
    return f"https://github.com/apps/{name}/installations/new"


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(current_user)):
    return MeResponse(
        id=str(user.id),
        github_login=user.github_login,
        email=user.email,
        avatar_url=user.avatar_url,
        install_url=_install_url(),
    )
