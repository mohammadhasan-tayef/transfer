"""Paths, constants, and environment configuration loaded from ``.env``."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / ".spyt"
BACKUP_FILE = DATA_DIR / "backup.json"
UNMATCHED_FILE = DATA_DIR / "unmatched.json"
SPOTIFY_CACHE = DATA_DIR / ".spotify_cache"
YTMUSIC_OAUTH_AUTH = DATA_DIR / "ytmusic_oauth.json"
YTMUSIC_BROWSER_AUTH = DATA_DIR / "ytmusic_headers.json"
ENV_FILE = PROJECT_ROOT / ".env"

SPOTIFY_SCOPES = (
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-follow-read",
)

# Pause between YouTube Music API calls to avoid throttling.
YTM_REQUEST_DELAY_SEC = 0.35

# Minimum fuzzy-match score (0-100) to accept a YouTube result.
MIN_MATCH_SCORE = 70


def ensure_data_dir() -> Path:
    """Create ``.spyt/`` runtime data directory if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def load_config() -> None:
    """Load variables from project ``.env`` into the process environment."""
    load_dotenv(ENV_FILE)


def get_spotify_pkce_config() -> tuple[str, str]:
    """Return ``(client_id, redirect_uri)`` for Spotify PKCE auth."""
    load_config()
    client_id = os.getenv("SPOTIPY_CLIENT_ID", "").strip()
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:9090").strip()
    if not client_id or client_id == "your_client_id_here":
        raise RuntimeError(
            "Set SPOTIPY_CLIENT_ID in .env from https://developer.spotify.com/dashboard"
        )
    if not redirect_uri:
        raise RuntimeError("Set SPOTIPY_REDIRECT_URI in .env (must match Spotify Dashboard exactly).")
    return client_id, redirect_uri


def get_spotify_credentials() -> tuple[str, str, str]:
    """Return ``(client_id, client_secret, redirect_uri)`` for Spotify OAuth."""
    load_config()
    client_id = os.getenv("SPOTIPY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:9090").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Spotify credentials for oauth mode. Set SPOTIPY_CLIENT_ID and "
            "SPOTIPY_CLIENT_SECRET in .env, or use SPOTIFY_AUTH_MODE=pkce (default)."
        )
    if client_id == "your_client_id_here":
        raise RuntimeError(
            "Replace the placeholder values in .env with your real Spotify app credentials."
        )
    return client_id, client_secret, redirect_uri


def get_ytmusic_credentials() -> tuple[str, str] | None:
    """Return Google OAuth credentials for YouTube Music, or ``None`` if unset."""
    load_config()
    client_id = os.getenv("YTMUSIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("YTMUSIC_CLIENT_SECRET", "").strip()
    if client_id and client_secret and not client_id.startswith("your_"):
        return client_id, client_secret
    return None


def get_spotify_auth_mode() -> str:
    """Return ``pkce`` (default) or ``oauth``."""
    load_config()
    mode = os.getenv("SPOTIFY_AUTH_MODE", "pkce").strip().lower()
    if mode in ("exportify", "custom"):
        mode = "pkce"
    if mode not in ("pkce", "oauth"):
        return "pkce"
    return mode


def get_proxies() -> dict[str, str]:
    """Return active HTTP(S) proxy dict for ``requests`` (via ``proxy`` module)."""
    from spyt.proxy import get_proxies as _get_proxies

    return _get_proxies()
