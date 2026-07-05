"""Spotify OAuth/PKCE authentication and Premium-policy error handling."""

from __future__ import annotations

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth, SpotifyPKCE

from spyt.config import (
    SPOTIFY_CACHE,
    SPOTIFY_SCOPES,
    get_proxies,
    get_spotify_auth_mode,
    get_spotify_credentials,
    get_spotify_pkce_config,
)


class SpotifyPremiumRequiredError(RuntimeError):
    """Spotify blocks library access for sandbox dev apps without Premium."""


class SpotifyRedirectUriError(RuntimeError):
    """OAuth redirect URI does not match the Spotify Developer Dashboard."""


def _is_premium_required_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "premium subscription required" in message or (
        isinstance(exc, SpotifyException) and exc.http_status == 403
    )


def _create_pkce_client(client_id: str, redirect_uri: str) -> spotipy.Spotify:
    proxies = get_proxies()
    auth = SpotifyPKCE(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=" ".join(SPOTIFY_SCOPES),
        cache_path=str(SPOTIFY_CACHE),
        open_browser=True,
        proxies=proxies or None,
    )
    return spotipy.Spotify(auth_manager=auth, requests_timeout=30)


def _create_oauth_client(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> spotipy.Spotify:
    proxies = get_proxies()
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SPOTIFY_SCOPES),
        cache_path=str(SPOTIFY_CACHE),
        open_browser=True,
        proxies=proxies or None,
    )
    return spotipy.Spotify(auth_manager=auth, requests_timeout=30)


def create_spotify_client() -> spotipy.Spotify:
    """Build an authenticated Spotipy client (PKCE or OAuth per ``.env``)."""
    mode = get_spotify_auth_mode()

    if mode == "oauth":
        client_id, client_secret, redirect_uri = get_spotify_credentials()
        return _create_oauth_client(client_id, client_secret, redirect_uri)

    client_id, redirect_uri = get_spotify_pkce_config()
    return _create_pkce_client(client_id, redirect_uri)


def create_spotify_client_with_fallback() -> spotipy.Spotify:
    return create_spotify_client()


def call_spotify(sp: spotipy.Spotify, method_name: str, *args, **kwargs):
    """Invoke a Spotipy method; translate Premium 403 into ``SpotifyPremiumRequiredError``."""
    try:
        return getattr(sp, method_name)(*args, **kwargs)
    except Exception as exc:
        if _is_premium_required_error(exc):
            raise SpotifyPremiumRequiredError(
                "Spotify blocked library access (developer app Premium policy). "
                "Export liked songs via https://exportify.app (with VPN), then run:\n"
                "  python -m spyt import-exportify your-export.zip\n"
                "  python -m spyt migrate-all --from-backup"
            ) from exc
        raise
