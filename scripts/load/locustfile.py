"""Basira load test profile.

Run from the backend container so the user sessions can reach the API on
the docker network:

    docker compose exec backend locust -f /app/scripts/load/locustfile.py \
        --headless -u 50 -r 5 -t 5m -H http://backend:8000

Each virtual user seeds itself a fresh user/repo via /test/seed once at
start, then walks the read-heavy dashboard endpoints. A small share of
requests start new scans so the worker queue gets exercised too.
"""
from __future__ import annotations

import random
import string

from locust import HttpUser, between, task


def _rand(prefix: str, n: int = 8) -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


class BasiraUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        login = _rand("loaduser-")
        repo = f"{login}/load-repo"
        r = self.client.post(
            "/test/seed",
            json={
                "github_login": login,
                "repo_full_name": repo,
                "private": False,
                "default_branch": "main",
                "with_api_key": True,
            },
            name="/test/seed (bootstrap)",
        )
        if r.status_code != 200:
            self.user_id = None
            self.repo_id = None
            return
        body = r.json()
        self.user_id = body["user_id"]
        self.repo_id = body["repo_id"]

    @task(10)
    def dashboard(self) -> None:
        self.client.get("/api/repos")

    @task(6)
    def scans_list(self) -> None:
        self.client.get("/api/scans")

    @task(4)
    def reviews_list(self) -> None:
        self.client.get("/api/reviews")

    @task(3)
    def api_keys(self) -> None:
        self.client.get("/api/me/api-keys")

    @task(2)
    def repo_detail(self) -> None:
        if not self.repo_id:
            return
        self.client.get(f"/api/repos/{self.repo_id}", name="/api/repos/[id]")

    @task(1)
    def start_scan(self) -> None:
        if not self.repo_id:
            return
        self.client.post(
            f"/api/repos/{self.repo_id}/scans",
            name="/api/repos/[id]/scans",
        )
