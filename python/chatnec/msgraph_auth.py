"""Shared MSAL device-code auth for adapters that act as a signed-in Microsoft
user (delegated Microsoft Graph permissions) rather than as a separate bot
identity — currently just TeamsUserAdapter, but written generically since any
future "acts as you" Microsoft 365 integration needs the same flow.

Requires an Azure AD app registration (public client, no secret) with the
delegated Graph permissions you're requesting consent for. Run
`chatnec teams-login` once to populate the token cache; after that,
acquire_token_silent() transparently refreshes without user interaction until
the refresh token itself expires or is revoked.

The token cache file contains a live refresh token — treat it like a
credential (default location is under your home directory, never inside the
repo).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def default_cache_path() -> str:
    return str(Path.home() / ".chatnec" / "msgraph_token_cache.json")


def _authority(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}"


def _load_cache(path: str):
    import msal

    cache = msal.SerializableTokenCache()
    if os.path.exists(path):
        cache.deserialize(Path(path).read_text(encoding="utf-8"))
    return cache


def _save_cache(path: str, cache) -> None:
    if cache.has_state_changed:
        cache_path = Path(path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize(), encoding="utf-8")


def device_code_login(
    client_id: str,
    tenant_id: str,
    scopes: list[str],
    cache_path: Optional[str] = None,
) -> None:
    """Interactive, one-time sign-in: prints a code + URL, blocks until you
    complete it in a browser, then caches the token (including a refresh
    token) so future runs don't need to repeat this. Intended to be run from
    `chatnec teams-login`, not from inside the server process.
    """
    import msal

    path = cache_path or default_cache_path()
    cache = _load_cache(path)
    app = msal.PublicClientApplication(client_id, authority=_authority(tenant_id), token_cache=cache)

    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to start device flow: {flow.get('error_description', flow)}")

    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)  # blocks until sign-in completes

    if "access_token" not in result:
        raise RuntimeError(f"Login failed: {result.get('error_description', result)}")

    _save_cache(path, cache)
    who = result.get("id_token_claims", {}).get("preferred_username", "(unknown account)")
    print(f"Signed in as {who}. Token cached at {path}.")


def acquire_token_silent(
    client_id: str,
    tenant_id: str,
    scopes: list[str],
    cache_path: Optional[str] = None,
) -> Optional[str]:
    """A valid access token from the cache, refreshing via the cached refresh
    token if needed. Returns None if there's no cached account — the caller
    should tell the user to run `chatnec teams-login`. Blocking (file I/O and,
    on refresh, a network call) — call via asyncio.to_thread from async code.
    """
    import msal

    path = cache_path or default_cache_path()
    cache = _load_cache(path)
    app = msal.PublicClientApplication(client_id, authority=_authority(tenant_id), token_cache=cache)

    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(scopes, account=accounts[0])
    _save_cache(path, cache)  # a refresh, if one happened, changed the cache state

    if result and "access_token" in result:
        return result["access_token"]
    return None
