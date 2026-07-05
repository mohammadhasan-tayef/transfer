"""Spotify Web API client for fetching library data."""

from __future__ import annotations

import spotipy

from spyt.spotify_auth import call_spotify, create_spotify_client_with_fallback
from spyt.models import Artist, Playlist, Track


def create_spotify_client() -> spotipy.Spotify:
    return create_spotify_client_with_fallback()


def _track_from_spotify(item: dict) -> Track | None:
    track = item.get("track") or item
    if not track or track.get("is_local"):
        return None
    artists = [a["name"] for a in track.get("artists", []) if a.get("name")]
    if not track.get("name") or not artists:
        return None
    return Track(
        title=track["name"],
        artists=artists,
        album=(track.get("album") or {}).get("name", ""),
        duration_ms=track.get("duration_ms") or 0,
        spotify_id=track.get("id") or "",
    )


def get_liked_songs(sp: spotipy.Spotify) -> list[Track]:
    """Paginate through the user's saved tracks."""
    tracks: list[Track] = []
    offset = 0
    while True:
        page = call_spotify(sp, "current_user_saved_tracks", limit=50, offset=offset)
        items = page.get("items") or []
        for item in items:
            track = _track_from_spotify(item)
            if track:
                tracks.append(track)
        if not page.get("next"):
            break
        offset += 50
    return tracks


def get_playlists(sp: spotipy.Spotify, include_liked: bool = True) -> list[Playlist]:
    """Fetch all user playlists; optionally prepend a synthetic Liked Songs playlist."""
    playlists: list[Playlist] = []

    if include_liked:
        liked = get_liked_songs(sp)
        playlists.append(
            Playlist(
                name="Liked Songs",
                description="Imported from Spotify liked songs",
                tracks=liked,
                is_liked_songs=True,
            )
        )

    offset = 0
    while True:
        page = call_spotify(sp, "current_user_playlists", limit=50, offset=offset)
        items = page.get("items") or []
        for pl in items:
            if not pl or not pl.get("id"):
                continue
            tracks = get_playlist_tracks(sp, pl["id"])
            playlists.append(
                Playlist(
                    name=pl.get("name") or "Untitled",
                    description=pl.get("description") or "",
                    tracks=tracks,
                    spotify_id=pl["id"],
                )
            )
        if not page.get("next"):
            break
        offset += 50

    return playlists


def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[Track]:
    tracks: list[Track] = []
    offset = 0
    while True:
        page = call_spotify(sp, "playlist_items", playlist_id, limit=100, offset=offset)
        items = page.get("items") or []
        for item in items:
            track = _track_from_spotify(item)
            if track:
                tracks.append(track)
        if not page.get("next"):
            break
        offset += 100
    return tracks


def get_followed_artists(sp: spotipy.Spotify) -> list[Artist]:
    """Paginate through artists the user follows."""
    artists: list[Artist] = []
    after: str | None = None
    while True:
        page = call_spotify(sp, "current_user_followed_artists", limit=50, after=after)
        items = (page.get("artists") or {}).get("items") or []
        for artist in items:
            if artist and artist.get("name"):
                artists.append(
                    Artist(
                        name=artist["name"],
                        spotify_id=artist.get("id") or "",
                    )
                )
        cursors = (page.get("artists") or {}).get("cursors") or {}
        after = cursors.get("after")
        if not after:
            break
    return artists
