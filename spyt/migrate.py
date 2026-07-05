"""Migration orchestration: backup export, track matching, and YouTube Music writes."""

from __future__ import annotations

import json
import time
from typing import Callable

from tqdm import tqdm

from spyt.config import BACKUP_FILE, UNMATCHED_FILE, YTM_REQUEST_DELAY_SEC, ensure_data_dir
from spyt.models import Artist, ArtistMatchResult, MatchResult, Playlist, Track
from spyt.spotify_client import (
    create_spotify_client,
    get_followed_artists,
    get_liked_songs,
    get_playlists,
)
from spyt.ytmusic_client import (
    add_liked_song,
    add_tracks_to_playlist,
    create_playlist,
    create_ytmusic_client,
    match_artist,
    match_track,
    subscribe_to_artist,
)


def export_backup(path: str | None = None) -> dict:
    """Fetch full Spotify library via API and write ``backup.json``."""
    sp = create_spotify_client()
    liked = get_liked_songs(sp)
    playlists = get_playlists(sp, include_liked=False)
    artists = get_followed_artists(sp)

    data = {
        "liked_songs": [t.to_dict() for t in liked],
        "playlists": [p.to_dict() for p in playlists],
        "artists": [a.to_dict() for a in artists],
    }

    ensure_data_dir()
    out = path or str(BACKUP_FILE)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def _load_backup(path: str | None = None) -> dict:
    backup_path = path or str(BACKUP_FILE)
    with open(backup_path, encoding="utf-8") as f:
        return json.load(f)


def _tracks_from_dict(items: list[dict]) -> list[Track]:
    return [
        Track(
            title=item["title"],
            artists=item.get("artists") or [],
            album=item.get("album", ""),
            duration_ms=item.get("duration_ms", 0),
            spotify_id=item.get("spotify_id", ""),
        )
        for item in items
    ]


def _artists_from_dict(items: list[dict]) -> list[Artist]:
    return [
        Artist(name=item["name"], spotify_id=item.get("spotify_id", ""))
        for item in items
    ]


def _playlists_from_dict(items: list[dict]) -> list[Playlist]:
    playlists: list[Playlist] = []
    for item in items:
        playlists.append(
            Playlist(
                name=item["name"],
                description=item.get("description", ""),
                tracks=_tracks_from_dict(item.get("tracks") or []),
                spotify_id=item.get("spotify_id", ""),
                is_liked_songs=item.get("is_liked_songs", False),
            )
        )
    return playlists


def _append_unmatched(kind: str, payload: dict) -> None:
    ensure_data_dir()
    existing: list[dict] = []
    if UNMATCHED_FILE.is_file():
        with open(UNMATCHED_FILE, encoding="utf-8") as f:
            existing = json.load(f)
    existing.append({"kind": kind, **payload})
    with open(UNMATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def _match_tracks(
    yt,
    tracks: list[Track],
    label: str,
    dry_run: bool,
    on_match: Callable[[str], None] | None = None,
) -> tuple[list[str], list[MatchResult]]:
    video_ids: list[str] = []
    unmatched: list[MatchResult] = []

    for track in tqdm(tracks, desc=label, unit="track"):
        result = match_track(yt, track)
        if result.video_id:
            video_ids.append(result.video_id)
            if not dry_run and on_match:
                on_match(result.video_id)
        else:
            unmatched.append(result)
            _append_unmatched("track", result.to_dict())

    return video_ids, unmatched


def migrate_liked_songs(
    *,
    dry_run: bool = False,
    use_backup: bool = False,
    backup_path: str | None = None,
) -> dict:
    """Match and optionally like each song from backup or Spotify API."""
    yt_lib = create_ytmusic_client() if not dry_run else None

    if use_backup:
        data = _load_backup(backup_path)
        tracks = _tracks_from_dict(data.get("liked_songs") or [])
    else:
        sp = create_spotify_client()
        tracks = get_liked_songs(sp)

    def like(video_id: str) -> None:
        add_liked_song(yt_lib, video_id)
        time.sleep(YTM_REQUEST_DELAY_SEC)

    matched_ids, unmatched = _match_tracks(
        None,
        tracks,
        label="Liked songs",
        dry_run=dry_run,
        on_match=None if dry_run else like,
    )

    return {
        "total": len(tracks),
        "matched": len(matched_ids),
        "unmatched": len(unmatched),
        "dry_run": dry_run,
    }


def migrate_playlists(
    *,
    dry_run: bool = False,
    use_backup: bool = False,
    backup_path: str | None = None,
    skip_liked: bool = True,
) -> dict:
    """Create YouTube Music playlists and fill them with matched tracks."""
    yt_lib = create_ytmusic_client() if not dry_run else None

    if use_backup:
        playlists = _playlists_from_dict((_load_backup(backup_path).get("playlists") or []))
    else:
        sp = create_spotify_client()
        playlists = get_playlists(sp, include_liked=False)

    summary = {"playlists": [], "dry_run": dry_run}

    for playlist in tqdm(playlists, desc="Playlists", unit="playlist"):
        if skip_liked and playlist.is_liked_songs:
            continue

        video_ids, unmatched = _match_tracks(
            None,
            playlist.tracks,
            label=f"Matching: {playlist.name[:40]}",
            dry_run=True,
        )

        entry = {
            "name": playlist.name,
            "total": len(playlist.tracks),
            "matched": len(video_ids),
            "unmatched": len(unmatched),
        }

        if not dry_run and video_ids:
            description = playlist.description or "Imported from Spotify"
            new_id = create_playlist(yt_lib, playlist.name, description)
            add_tracks_to_playlist(yt_lib, new_id, video_ids)
            entry["youtube_playlist_id"] = new_id
            time.sleep(YTM_REQUEST_DELAY_SEC)

        summary["playlists"].append(entry)

    return summary


def migrate_artists(
    *,
    dry_run: bool = False,
    use_backup: bool = False,
    backup_path: str | None = None,
) -> dict:
    """Match and optionally subscribe to followed artists."""
    yt_lib = create_ytmusic_client() if not dry_run else None

    if use_backup:
        artists = _artists_from_dict((_load_backup(backup_path).get("artists") or []))
    else:
        sp = create_spotify_client()
        artists = get_followed_artists(sp)

    matched = 0
    unmatched: list[ArtistMatchResult] = []

    for artist in tqdm(artists, desc="Artists", unit="artist"):
        result = match_artist(None, artist)
        if result.channel_id:
            matched += 1
            if not dry_run:
                subscribe_to_artist(yt_lib, result.channel_id)
                time.sleep(YTM_REQUEST_DELAY_SEC)
        else:
            unmatched.append(result)
            _append_unmatched("artist", result.to_dict())

    return {
        "total": len(artists),
        "matched": matched,
        "unmatched": len(unmatched),
        "dry_run": dry_run,
    }


def migrate_all(
    *,
    dry_run: bool = False,
    use_backup: bool = False,
    backup_path: str | None = None,
) -> dict:
    """Run liked-songs, playlist, and artist migration in sequence."""
    return {
        "liked_songs": migrate_liked_songs(
            dry_run=dry_run, use_backup=use_backup, backup_path=backup_path
        ),
        "playlists": migrate_playlists(
            dry_run=dry_run, use_backup=use_backup, backup_path=backup_path
        ),
        "artists": migrate_artists(
            dry_run=dry_run, use_backup=use_backup, backup_path=backup_path
        ),
    }
