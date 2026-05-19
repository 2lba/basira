from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger
from app.integrations.github_app import GithubAppError, get_installation_token

log = get_logger("reviewly.github_api")

GH_API = "https://api.github.com"
DIFF_MEDIA = "application/vnd.github.v3.diff"
JSON_MEDIA = "application/vnd.github+json"


class GithubApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


@dataclass(frozen=True)
class PrFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None
    sha: str | None
    previous_filename: str | None = None


_RETRYABLE = (httpx.TransportError, httpx.RemoteProtocolError)


def _retry():
    return retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )


class InstallationClient:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id

    async def _headers(self, accept: str = JSON_MEDIA) -> dict[str, str]:
        token = await get_installation_token(self.installation_id)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "reviewly/0.1",
        }

    @_retry()
    async def _get(self, path: str, accept: str = JSON_MEDIA, params: dict | None = None):
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{GH_API}{path}",
                headers=await self._headers(accept),
                params=params,
            )
        if r.status_code >= 400:
            raise GithubApiError(r.status_code, r.text[:500])
        return r

    @_retry()
    async def _post(self, path: str, body: dict, accept: str = JSON_MEDIA):
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GH_API}{path}",
                headers=await self._headers(accept),
                json=body,
            )
        if r.status_code >= 400:
            raise GithubApiError(r.status_code, r.text[:500])
        return r

    @_retry()
    async def _patch(self, path: str, body: dict, accept: str = JSON_MEDIA):
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.patch(
                f"{GH_API}{path}",
                headers=await self._headers(accept),
                json=body,
            )
        if r.status_code >= 400:
            raise GithubApiError(r.status_code, r.text[:500])
        return r

    async def get_pr(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        r = await self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        return r.json()

    async def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        r = await self._get(f"/repos/{owner}/{repo}/pulls/{number}", accept=DIFF_MEDIA)
        return r.text

    async def list_pr_files(
        self, owner: str, repo: str, number: int, max_pages: int = 30
    ) -> list[PrFile]:
        out: list[PrFile] = []
        page = 1
        while page <= max_pages:
            r = await self._get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            items = r.json()
            if not items:
                break
            for it in items:
                out.append(
                    PrFile(
                        filename=it["filename"],
                        status=it.get("status", "modified"),
                        additions=int(it.get("additions", 0)),
                        deletions=int(it.get("deletions", 0)),
                        changes=int(it.get("changes", 0)),
                        patch=it.get("patch"),
                        sha=it.get("sha"),
                        previous_filename=it.get("previous_filename"),
                    )
                )
            if len(items) < 100:
                break
            page += 1
        return out

    async def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        commit_id: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments
        r = await self._post(f"/repos/{owner}/{repo}/pulls/{number}/reviews", payload)
        return r.json()

    async def list_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        r = await self._get(f"/repos/{owner}/{repo}/pulls/{number}/reviews")
        return r.json()

    async def update_review_body(
        self,
        owner: str,
        repo: str,
        number: int,
        review_id: int,
        body: str,
    ) -> dict[str, Any]:
        r = await self._put(
            f"/repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}",
            {"body": body},
        )
        return r.json()

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        r = await self._get(f"/repos/{owner}/{repo}")
        return r.json()

    async def get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        r = await self._get(f"/repos/{owner}/{repo}/branches/{branch}")
        return str(r.json()["commit"]["sha"])

    async def get_tree(
        self, owner: str, repo: str, sha: str, recursive: bool = True
    ) -> list[dict[str, Any]]:
        params = {"recursive": "1"} if recursive else None
        r = await self._get(f"/repos/{owner}/{repo}/git/trees/{sha}", params=params)
        data = r.json()
        return list(data.get("tree", []) or [])

    async def get_blob_text(self, owner: str, repo: str, sha: str) -> str:
        """Fetches a blob and returns its decoded text. Returns '' for binary or
        encodings we can't handle."""
        import base64

        r = await self._get(f"/repos/{owner}/{repo}/git/blobs/{sha}")
        data = r.json()
        if data.get("encoding") != "base64":
            return ""
        try:
            raw = base64.b64decode(data.get("content", ""), validate=False)
        except Exception:
            return ""
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return ""

    @_retry()
    async def _put(self, path: str, body: dict, accept: str = JSON_MEDIA):
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.put(
                f"{GH_API}{path}",
                headers=await self._headers(accept),
                json=body,
            )
        if r.status_code >= 400:
            raise GithubApiError(r.status_code, r.text[:500])
        return r


async def installation_client(installation_id: int) -> InstallationClient:
    if not installation_id:
        raise GithubAppError("installation_id required")
    return InstallationClient(installation_id)
