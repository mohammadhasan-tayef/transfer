"""YouTube Music client setup, dual auth clients, and library write helpers."""

from __future__ import annotations

from ytmusicapi import YTMusic
from ytmusicapi.auth.browser import setup_browser
from ytmusicapi.exceptions import YTMusicServerError

from spyt.config import YTMUSIC_BROWSER_AUTH, YTMUSIC_OAUTH_AUTH, ensure_data_dir, get_proxies
from spyt.curl_headers import headers_from_curl, is_curl_input
from spyt.matcher import find_artist_match, find_song_match, like_song
from spyt.models import Artist, ArtistMatchResult, MatchResult, Track

_search_client: YTMusic | None = None


def ytmusic_auth_exists() -> bool:
    """Return True if browser or OAuth credentials are saved on disk."""
    return YTMUSIC_BROWSER_AUTH.is_file() or YTMUSIC_OAUTH_AUTH.is_file()


def ytmusic_auth_mode() -> str | None:
    if YTMUSIC_BROWSER_AUTH.is_file():
        return "browser"
    if YTMUSIC_OAUTH_AUTH.is_file():
        return "oauth"
    return None


def _client_works(yt: YTMusic) -> bool:
    """Check whether an authenticated client can read private library data."""
    # Some accounts return 400 on get_account_info despite valid session cookies.
    # Library endpoints are a better indicator for migration readiness.
    for check in (
        lambda: yt.get_library_playlists(limit=1),
        lambda: yt.get_library_songs(limit=1),
    ):
        try:
            check()
            return True
        except Exception:
            continue

    try:
        yt.get_account_info()
        return True
    except YTMusicServerError as exc:
        if "400" in str(exc):
            return False
        raise
    except Exception:
        return False


def _read_multiline_input() -> str:
    print()
    print("Paste from Chrome, then press Enter, Ctrl+Z, Enter:")
    print("  • Copy → Copy as cURL (cmd)   OR")
    print("  • Headers tab → Request Headers → select all → copy")
    print()
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        lines.append(line)
    return "\n".join(lines)


def setup_ytmusic_auth() -> None:
    """Set up YouTube Music using browser cookies from Chrome."""
    ensure_data_dir()
    print("YouTube Music setup (Chrome)")
    print()
    print("IMPORTANT: Do NOT copy the first music.youtube.com page load.")
    print("That request has no cookies. Use an API request instead:")
    print()
    print("  1. On music.youtube.com, click Library or any playlist")
    print("  2. DevTools → Network → filter box type: browse")
    print("  3. Click a POST request containing: youtubei/v1/browse")
    print("  4. Right-click it → Copy → Copy as cURL (cmd)")
    print("  5. Paste below — the cURL MUST contain 'cookie'")
    print()

    pasted = _read_multiline_input().strip()
    if not pasted:
        raise RuntimeError("Nothing pasted.")

    if is_curl_input(pasted):
        headers_raw = headers_from_curl(pasted)
    else:
        headers_raw = pasted

    if "cookie" not in headers_raw.lower():
        raise RuntimeError(
            "No cookie found in pasted data.\n"
            "You copied the wrong request. Filter Network by 'browse', click\n"
            "youtubei/v1/browse, then Copy as cURL (cmd) again."
        )

    setup_browser(str(YTMUSIC_BROWSER_AUTH), headers_raw=headers_raw)
    yt = YTMusic(str(YTMUSIC_BROWSER_AUTH), proxies=get_proxies() or None)
    if not _client_works(yt):
        raise RuntimeError(
            "Headers saved but login test failed.\n"
            "Try again with the music.youtube.com request (not collect/analytics)."
        )
    print(f"YouTube Music credentials saved to {YTMUSIC_BROWSER_AUTH}")


def create_ytmusic_search_client() -> YTMusic:
    """Unauthenticated client — used for searching/matching tracks."""
    global _search_client
    if _search_client is None:
        _search_client = YTMusic(proxies=get_proxies() or None)
    return _search_client


def create_ytmusic_client() -> YTMusic:
    """Authenticated client — required to like songs and create playlists."""
    proxies = get_proxies() or None
    # Browser headers are the primary auth path for this project.
    # Do not preflight-check aggressively here because some sessions fail read probes
    # but still work for migration actions.
    if YTMUSIC_BROWSER_AUTH.is_file():
        return YTMusic(str(YTMUSIC_BROWSER_AUTH), proxies=proxies)

    # OAuth is legacy in spyt; only use it when browser auth is not configured.
    if not YTMUSIC_BROWSER_AUTH.is_file() and YTMUSIC_OAUTH_AUTH.is_file():
        try:
            yt = YTMusic(str(YTMUSIC_OAUTH_AUTH), proxies=proxies)
            if _client_works(yt):
                return yt
        except Exception as exc:
            raise RuntimeError(
                "YouTube Music OAuth config is invalid. Re-run browser setup:\n"
                "  python -m spyt setup-ytmusic"
            ) from exc

    raise RuntimeError(
        "YouTube Music auth is missing or broken. Run:\n"
        "  python -m spyt setup-ytmusic\n"
        "If VPN/proxy is on, keep it active in both browser and terminal."
    )


def match_track(_yt: YTMusic | None, track: Track) -> MatchResult:
    """Delegate to ``find_song_match`` using the unauthenticated search client."""
    return find_song_match(create_ytmusic_search_client(), track)


def match_artist(_yt: YTMusic | None, artist: Artist) -> ArtistMatchResult:
    return find_artist_match(create_ytmusic_search_client(), artist)


def add_liked_song(yt: YTMusic, video_id: str) -> None:
    like_song(yt, video_id)


def subscribe_to_artist(yt: YTMusic, channel_id: str) -> None:
    yt.subscribe_artists([channel_id])


def create_playlist(yt: YTMusic, title: str, description: str = "") -> str:
    """Create a new YouTube Music playlist and return its ID."""
    return yt.create_playlist(title, description)


def get_playlist_video_ids(yt: YTMusic, playlist_id: str) -> set[str]:
    """Return video IDs already present in a YouTube Music playlist."""
    try:
        details = yt.get_playlist(playlist_id, limit=None)
    except Exception:
        return set()
    ids: set[str] = set()
    for track in details.get("tracks") or []:
        video_id = track.get("videoId")
        if video_id:
            ids.add(video_id)
    return ids


def add_tracks_to_playlist(
    yt: YTMusic, playlist_id: str, video_ids: list[str], batch_size: int = 10
) -> None:
    """Add video IDs to a playlist in small batches with retries."""
    import time

    from spyt.config import YTM_REQUEST_DELAY_SEC

    existing = get_playlist_video_ids(yt, playlist_id)
    to_add = [vid for vid in video_ids if vid and vid not in existing]
    if not to_add:
        return

    for i in range(0, len(to_add), batch_size):
        batch = to_add[i : i + batch_size]
        for attempt in range(5):
            try:
                yt.add_playlist_items(playlist_id, batch, duplicates=False)
                break
            except Exception as exc:
                msg = str(exc)
                retryable = any(
                    token in msg
                    for token in ("409", "429", "timed out", "Timeout", "SSL", "Max retries")
                )
                if retryable and attempt < 4:
                    time.sleep(2 + attempt * 2)
                    continue
                raise
        time.sleep(YTM_REQUEST_DELAY_SEC)
