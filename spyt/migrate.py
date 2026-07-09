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


def _existing_playlist_ids(yt) -> dict[str, str]:
    """Map lowercased playlist title → YouTube playlist ID.

    If duplicate titles exist (from interrupted/raced migrations), prefer the
    playlist that already has the most tracks so we refill the fullest copy.
    """
    from spyt.ytmusic_client import get_playlist_video_ids

    best: dict[str, tuple[str, int]] = {}
    try:
        for item in yt.get_library_playlists(limit=100) or []:
            title = (item.get("title") or "").strip()
            playlist_id = item.get("playlistId")
            if not title or not playlist_id or playlist_id in ("LM", "SE"):
                continue
            key = title.casefold()
            try:
                count = len(get_playlist_video_ids(yt, playlist_id))
            except Exception:
                count = int(item.get("count") or 0)
            prev = best.get(key)
            if prev is None or count >= prev[1]:
                best[key] = (playlist_id, count)
    except Exception:
        pass
    return {key: playlist_id for key, (playlist_id, _) in best.items()}


def _playlist_track_count(yt, playlist_id: str) -> int:
    try:
        details = yt.get_playlist(playlist_id, limit=None)
        return len(details.get("tracks") or [])
    except Exception:
        return 0


def migrate_playlists(
    *,
    dry_run: bool = False,
    use_backup: bool = False,
    backup_path: str | None = None,
    skip_liked: bool = True,
) -> dict:
    """Create YouTube Music playlists and fill them with matched tracks."""
    from spyt.ytmusic_client import get_playlist_video_ids

    yt_lib = create_ytmusic_client() if not dry_run else None
    existing = _existing_playlist_ids(yt_lib) if yt_lib else {}

    if use_backup:
        playlists = _playlists_from_dict((_load_backup(backup_path).get("playlists") or []))
    else:
        sp = create_spotify_client()
        playlists = get_playlists(sp, include_liked=False)

    summary = {"playlists": [], "dry_run": dry_run}

    for playlist in tqdm(playlists, desc="Playlists", unit="playlist"):
        if skip_liked and playlist.is_liked_songs:
            continue

        key = playlist.name.casefold()
        already_id = existing.get(key)
        expected = len(playlist.tracks)

        # Skip only fully complete playlists to avoid rematching for hours.
        if already_id and not dry_run:
            current_count = _playlist_track_count(yt_lib, already_id)
            if expected and current_count >= int(expected * 0.95):
                summary["playlists"].append(
                    {
                        "name": playlist.name,
                        "total": expected,
                        "matched": current_count,
                        "unmatched": 0,
                        "youtube_playlist_id": already_id,
                        "skipped": "already complete",
                    }
                )
                print(f"\n[spyt] Skipping complete playlist: {playlist.name} ({current_count}/{expected})")
                continue

        video_ids, unmatched = _match_tracks(
            None,
            playlist.tracks,
            label=f"Matching: {playlist.name[:40]}",
            dry_run=True,
        )

        entry = {
            "name": playlist.name,
            "total": expected,
            "matched": len(video_ids),
            "unmatched": len(unmatched),
        }

        if not dry_run and video_ids:
            description = playlist.description or "Imported from Spotify"
            try:
                if already_id:
                    new_id = already_id
                    entry["reused"] = True
                    already_present = get_playlist_video_ids(yt_lib, new_id)
                    missing = [vid for vid in video_ids if vid not in already_present]
                    entry["already_present"] = len(already_present)
                    entry["to_add"] = len(missing)
                    print(
                        f"\n[spyt] Refilling {playlist.name}: "
                        f"{len(already_present)} present, {len(missing)} missing"
                    )
                    add_tracks_to_playlist(yt_lib, new_id, missing)
                else:
                    new_id = create_playlist(yt_lib, playlist.name, description)
                    existing[key] = new_id
                    time.sleep(YTM_REQUEST_DELAY_SEC * 2)
                    add_tracks_to_playlist(yt_lib, new_id, video_ids)
                final_count = _playlist_track_count(yt_lib, new_id)
                entry["youtube_playlist_id"] = new_id
                entry["final_count"] = final_count
                time.sleep(YTM_REQUEST_DELAY_SEC)
            except Exception as exc:
                entry["error"] = str(exc)
                print(f"\n[spyt] Failed on playlist '{playlist.name}': {exc}")
                print("[spyt] Continuing with remaining playlists...")
                time.sleep(3)

        summary["playlists"].append(entry)

    return summary


def verify_and_refill_playlists(
    *,
    backup_path: str | None = None,
    complete_ratio: float = 0.98,
) -> dict:
    """After migration: check every playlist and add any still-missing matched tracks.

    Skips playlists that are already nearly complete. Logs unmatched tracks.
    """
    from spyt.matcher import find_song_match
    from spyt.ytmusic_client import (
        create_ytmusic_search_client,
        get_playlist_video_ids,
    )

    playlists = _playlists_from_dict((_load_backup(backup_path).get("playlists") or []))
    yt_lib = create_ytmusic_client()
    search = create_ytmusic_search_client()

    report: dict = {"playlists": [], "created": 0, "refilled": 0, "complete": 0, "failed": 0}

    print("\n[spyt] Post-migration verify: checking all playlists for missing tracks...")
    print("[spyt] If duplicates exist, the fullest playlist is used (no new duplicates).")

    for playlist in tqdm(playlists, desc="Verify/refill", unit="playlist"):
        if playlist.is_liked_songs:
            continue

        key = playlist.name.casefold()
        expected = len(playlist.tracks)
        entry: dict = {
            "name": playlist.name,
            "backup": expected,
            "before": 0,
            "added": 0,
            "final": 0,
            "unmatched": 0,
        }

        try:
            # Re-scan each time so we never create a duplicate while another job runs.
            existing = _existing_playlist_ids(yt_lib)
            playlist_id = existing.get(key)
            if not playlist_id:
                print(f"\n[spyt] Creating missing playlist: {playlist.name}")
                playlist_id = create_playlist(
                    yt_lib,
                    playlist.name,
                    playlist.description or "Imported from Spotify",
                )
                report["created"] += 1
                time.sleep(YTM_REQUEST_DELAY_SEC * 2)

            present = get_playlist_video_ids(yt_lib, playlist_id)
            entry["before"] = len(present)
            if expected and len(present) >= int(expected * complete_ratio):
                entry["final"] = len(present)
                entry["status"] = "complete"
                report["complete"] += 1
                print(
                    f"\n[spyt] OK {playlist.name}: {len(present)}/{expected}"
                )
                report["playlists"].append(entry)
                continue

            print(
                f"\n[spyt] Incomplete {playlist.name}: "
                f"{len(present)}/{expected} — rematching missing tracks..."
            )
            to_add: list[str] = []
            unmatched = 0
            for track in playlist.tracks:
                result = find_song_match(search, track)
                if not result.video_id:
                    unmatched += 1
                    _append_unmatched("track", result.to_dict())
                    continue
                if result.video_id not in present:
                    to_add.append(result.video_id)

            # de-dupe while preserving order
            seen: set[str] = set()
            unique = []
            for vid in to_add:
                if vid not in seen:
                    seen.add(vid)
                    unique.append(vid)

            if unique:
                add_tracks_to_playlist(yt_lib, playlist_id, unique, batch_size=5)
                report["refilled"] += 1
                time.sleep(YTM_REQUEST_DELAY_SEC)

            final_ids = get_playlist_video_ids(yt_lib, playlist_id)
            entry["added"] = len(unique)
            entry["final"] = len(final_ids)
            entry["unmatched"] = unmatched
            entry["status"] = (
                "complete"
                if expected and len(final_ids) >= int(expected * complete_ratio)
                else "incomplete"
            )
            if entry["status"] == "complete":
                report["complete"] += 1
            print(
                f"[spyt] {playlist.name}: before={entry['before']} "
                f"added={entry['added']} final={entry['final']}/{expected} "
                f"unmatched={unmatched}"
            )
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
            report["failed"] += 1
            print(f"\n[spyt] Verify failed for '{playlist.name}': {exc}")
            time.sleep(2)

        report["playlists"].append(entry)

    print(
        f"\n[spyt] Verify done — complete={report['complete']} "
        f"refilled={report['refilled']} created={report['created']} "
        f"failed={report['failed']}"
    )
    return report


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
