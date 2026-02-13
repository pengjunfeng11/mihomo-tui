from __future__ import annotations

import httpx

from .config import get_external_controller, get_secret


def _base_url() -> str:
    host, port = get_external_controller()
    return f"http://{host}:{port}"


def _headers() -> dict[str, str]:
    secret = get_secret()
    if secret:
        return {"Authorization": f"Bearer {secret}"}
    return {}


async def get_proxies(client: httpx.AsyncClient) -> dict:
    r = await client.get(f"{_base_url()}/proxies", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


async def get_proxy_group(client: httpx.AsyncClient, group: str) -> dict:
    r = await client.get(
        f"{_base_url()}/proxies/{group}", headers=_headers(), timeout=5
    )
    r.raise_for_status()
    return r.json()


async def switch_proxy(client: httpx.AsyncClient, group: str, name: str) -> None:
    r = await client.put(
        f"{_base_url()}/proxies/{group}",
        headers=_headers(),
        json={"name": name},
        timeout=5,
    )
    r.raise_for_status()


async def test_delay(
    client: httpx.AsyncClient,
    name: str,
    timeout_ms: int = 5000,
    url: str = "http://www.gstatic.com/generate_204",
) -> int | None:
    """Return delay in ms, or None on failure."""
    try:
        r = await client.get(
            f"{_base_url()}/proxies/{name}/delay",
            headers=_headers(),
            params={"timeout": timeout_ms, "url": url},
            timeout=timeout_ms / 1000 + 2,
        )
        if r.status_code == 200:
            return r.json().get("delay")
    except (httpx.HTTPError, httpx.TimeoutException):
        pass
    return None


async def get_configs(client: httpx.AsyncClient) -> dict:
    r = await client.get(f"{_base_url()}/configs", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


async def patch_configs(client: httpx.AsyncClient, patch: dict) -> None:
    r = await client.patch(
        f"{_base_url()}/configs",
        headers=_headers(),
        json=patch,
        timeout=5,
    )
    r.raise_for_status()
