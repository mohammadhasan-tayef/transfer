"""Fuzzy track/artist matching against YouTube Music search results."""

from __future__ import annotations

import re
import time

from thefuzz import fuzz
from ytmusicapi import YTMusic
from ytmusicapi.models.content.enums import LikeStatus

from spyt.config import MIN_MATCH_SCORE, YTM_REQUEST_DELAY_SEC
from spyt.models import Artist, ArtistMatchResult, MatchResult, Track


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _artist_names(result: dict) -> list[str]:
    names: list[str] = []
    for artist in result.get("artists") or []:
        if isinstance(artist, dict) and artist.get("name"):
            names.append(artist["name"])
        elif isinstance(artist, str):
            names.append(artist)
    return names


def _duration_seconds(result: dict) -> int | None:
    if result.get("duration_seconds") is not None:
        return int(result["duration_seconds"])
    duration = result.get("duration")
    if not duration or ":" not in duration:
        return None
    parts = duration.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def _score_track(track: Track, result: dict) -> int:
    result_type = result.get("resultType", "")
    if result_type not in ("song", "video"):
        return 0

    title_score = fuzz.token_set_ratio(
        _normalize(track.title), _normalize(result.get("title", ""))
    )

    result_artists = _artist_names(result)
    if track.artists and result_artists:
        spotify_artist = _normalize(track.artists[0])
        best_artist = max(
            fuzz.token_set_ratio(spotify_artist, _normalize(name))
            for name in result_artists
        )
    else:
        best_artist = 0

    duration_score = 50
    yt_seconds = _duration_seconds(result)
    if track.duration_ms and yt_seconds:
        spotify_seconds = track.duration_ms // 1000
        diff = abs(spotify_seconds - yt_seconds)
        if diff <= 3:
            duration_score = 100
        elif diff <= 8:
            duration_score = 85
        elif diff <= 20:
            duration_score = 65
        else:
            duration_score = 30

    type_bonus = 10 if result_type == "song" else 0
    return int(title_score * 0.5 + best_artist * 0.35 + duration_score * 0.15 + type_bonus)


def _search_queries(track: Track) -> list[str]:
    primary_artist = track.artists[0] if track.artists else ""
    queries = [
        f"{track.title} {primary_artist}",
        f"{primary_artist} {track.title}",
        track.title,
    ]
    if track.album:
        queries.append(f"{track.title} {track.album}")
    # Extra artists help when first artist is a feature credit
    if len(track.artists) > 1:
        queries.append(f"{track.title} {track.artists[1]}")
        queries.append(f"{' '.join(track.artists[:2])} {track.title}")
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        key = query.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(query.strip())
    return unique


def _search_with_retry(
    yt: YTMusic, query: str, *, filter: str | None = "songs", retries: int = 4
) -> list[dict]:
    """Search with retries for proxy/timeout SSL failures."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            kwargs = {"filter": filter} if filter else {}
            return yt.search(query, limit=10, **kwargs) or []
        except Exception as exc:
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    if last_exc:
        raise last_exc
    return []


def find_song_match(yt: YTMusic, track: Track) -> MatchResult:
    """Search YouTube Music and return the best fuzzy match above ``MIN_MATCH_SCORE``."""
    best: dict | None = None
    best_score = 0

    # Prefer songs, then fall back to broader search for hard-to-find tracks.
    for filter_name in ("songs", None):
        for query in _search_queries(track):
            results = _search_with_retry(yt, query, filter=filter_name)
            time.sleep(YTM_REQUEST_DELAY_SEC)
            for result in results:
                score = _score_track(track, result)
                if score > best_score:
                    best = result
                    best_score = score
            if best_score >= 90:
                break
        if best_score >= MIN_MATCH_SCORE:
            break

    if best and best_score >= MIN_MATCH_SCORE:
        return MatchResult(
            track=track,
            video_id=best.get("videoId"),
            matched_title=best.get("title", ""),
            score=best_score,
        )

    return MatchResult(track=track, video_id=None, score=best_score)


def find_artist_match(yt: YTMusic, artist: Artist) -> ArtistMatchResult:
    """Search YouTube Music artists and return the best name match."""
    results = yt.search(artist.name, filter="artists", limit=8)
    time.sleep(YTM_REQUEST_DELAY_SEC)

    best: dict | None = None
    best_score = 0
    for result in results:
        name = result.get("artist") or result.get("title") or ""
        score = fuzz.token_set_ratio(_normalize(artist.name), _normalize(name))
        if score > best_score:
            best = result
            best_score = score

    channel_id = None
    matched_name = ""
    if best and best_score >= MIN_MATCH_SCORE:
        channel_id = best.get("browseId") or best.get("channelId")
        matched_name = best.get("artist") or best.get("title") or ""

    return ArtistMatchResult(
        artist=artist,
        channel_id=channel_id,
        matched_name=matched_name,
        score=best_score,
    )


def like_song(yt: YTMusic, video_id: str) -> None:
    """Rate a YouTube Music video as liked (thumbs up)."""
    yt.rate_song(video_id, rating=LikeStatus.LIKE)
    time.sleep(YTM_REQUEST_DELAY_SEC)
