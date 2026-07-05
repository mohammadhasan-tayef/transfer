"""YouTube Music client setup, dual auth clients, and library write helpers."""

from __future__ import annotations
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

    if YTMUSIC_BROWSER_AUTH.is_file():
        yt = YTMusic(str(YTMUSIC_BROWSER_AUTH), proxies=proxies)
        if _client_works(yt):
            return yt

    if YTMUSIC_OAUTH_AUTH.is_file():
        yt = YTMusic(str(YTMUSIC_OAUTH_AUTH), proxies=proxies)
        if _client_works(yt):
            return yt

    raise RuntimeError(
        "YouTube Music auth is missing or broken. Run:\n"
        "  python -m spyt setup-ytmusic"
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


def add_tracks_to_playlist(
    yt: YTMusic, playlist_id: str, video_ids: list[str], batch_size: int = 25
) -> None:
    """Add video IDs to a playlist in batches (YouTube API limit ~25 per call)."""
    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i : i + batch_size]
        yt.add_playlist_items(playlist_id, batch, duplicates=False)
