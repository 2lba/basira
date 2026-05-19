import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from app.config import get_settings

GH_API = "https://api.github.com"


class GithubAppError(Exception):
    pass


@dataclass
class InstallationToken:
    token: str
    expires_at: datetime

    def expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at - timedelta(minutes=2)


_token_cache: dict[int, InstallationToken] = {}


def _load_private_key() -> str:
    s = get_settings()
    path = s.github_app_private_key_path
    if not path:
        raise GithubAppError("GITHUB_APP_PRIVATE_KEY_PATH not configured")
    p = Path(path)
    if not p.exists():
        raise GithubAppError(f"private key file not found: {path}")
    # safety: warn if file is world-readable (chmod 600 expected in prod)
    try:
        mode = p.stat().st_mode & 0o777
        if mode & 0o077 and s.is_production:
            raise GithubAppError(
                f"private key {path} has loose perms {oct(mode)}; chmod 600 required"
            )
    except OSError:
        pass
    return p.read_text()


def app_jwt() -> str:
    s = get_settings()
    if not s.github_app_id:
        raise GithubAppError("GITHUB_APP_ID not configured")
    now = int(time.time())
    payload = {
        "iat": now - 30,
        "exp": now + 9 * 60,
        "iss": s.github_app_id,
    }
    pk = _load_private_key()
    return jwt.encode(payload, pk, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    cached = _token_cache.get(installation_id)
    if cached and not cached.expired():
        return cached.token

    headers = {
        "Authorization": f"Bearer {app_jwt()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        r = await client.post(f"{GH_API}/app/installations/{installation_id}/access_tokens")
    if r.status_code != 201:
        raise GithubAppError(f"installation token failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    token = body.get("token")
    expires_at_str = body.get("expires_at")
    if not token or not expires_at_str:
        raise GithubAppError("malformed installation token response")
    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    _token_cache[installation_id] = InstallationToken(token=token, expires_at=expires_at)
    return token


def reset_installation_cache(installation_id: int | None = None) -> None:
    if installation_id is None:
        _token_cache.clear()
    else:
        _token_cache.pop(installation_id, None)
