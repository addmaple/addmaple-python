from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from addmaple.dataset import Dataset


def _resolve_token(token: str | None) -> str | None:
    if token:
        return token
    env = os.environ.get("ADDMAPLE_TOKEN", "").strip()
    return env or None


@dataclass
class AddMapleClient:
    base_url: str
    token: str | None = None
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    _client: httpx.Client | None = field(default=None, repr=False)

    def _http(self) -> httpx.Client:
        if self._client is None:
            headers: dict[str, str] = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            client_kwargs: dict = {
                "base_url": self.base_url.rstrip("/"),
                "headers": headers,
                "timeout": 120.0,
            }
            if self.transport is not None:
                client_kwargs["transport"] = self.transport
            self._client = httpx.Client(**client_kwargs)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def list_projects(self) -> list[dict[str, Any]]:
        if not self.token:
            raise ValueError(
                "list_projects() requires a bearer token; pass token= to connect() "
                "or set ADDMAPLE_TOKEN"
            )
        response = self._http().get("/api/engine-v2/projects")
        response.raise_for_status()
        payload = response.json()
        projects = payload.get("projects")
        if not isinstance(projects, list):
            raise ValueError("Unexpected list projects response shape")
        return projects

    def dataset(self, project_id: str) -> Dataset:
        from addmaple.dataset import Dataset

        return Dataset(client=self, project_id=project_id)


def connect(
    base_url: str,
    *,
    token: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> AddMapleClient:
    return AddMapleClient(
        base_url=base_url,
        token=_resolve_token(token),
        transport=transport,
    )
