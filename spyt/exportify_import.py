"""Import Spotify library data from Exportify CSV/ZIP exports."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from spyt.config import BACKUP_FILE, ensure_data_dir
from spyt.models import Artist, Playlist, Track


def _parse_duration(value: str) -> int:
    value = (value or "").strip()
    if not value:
        return 0
    if value.isdigit():
        return int(value)
    if ":" in value:
        parts = value.split(":")
        try:
            if len(parts) == 2:
                return (int(parts[0]) * 60 + int(parts[1])) * 1000
            if len(parts) == 3:
                return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
        except ValueError:
            return 0
    return 0


def _split_artists(value: str) -> list[str]:
    if not value:
        return []
    for sep in (";", "|", "/"):
        if sep in value:
            return [a.strip() for a in value.split(sep) if a.strip()]
    if "," in value:
        return [a.strip() for a in value.split(",") if a.strip()]
    return [value.strip()] if value.strip() else []


def _track_from_row(row: dict[str, str]) -> Track | None:
    title = (
        row.get("Track Name")
        or row.get("track name")
        or row.get("Name")
        or row.get("name")
        or ""
    ).strip()
    artists_raw = (
        row.get("Artist Name(s)")
        or row.get("Artist Name")
        or row.get("Artists")
        or row.get("artist")
        or ""
    )
    artists = _split_artists(artists_raw)
    if not title or not artists:
        return None

    album = (
        row.get("Album Name") or row.get("Album") or row.get("album") or ""
    ).strip()
    duration = _parse_duration(
        row.get("Duration (ms)")
        or row.get("Track Duration (ms)")
        or row.get("Duration")
        or row.get("duration_ms")
        or ""
    )
    spotify_id = ""
    uri = row.get("Track URI") or row.get("Spotify URI") or row.get("URI") or ""
    if uri and "spotify:track:" in uri:
        spotify_id = uri.rsplit(":", 1)[-1]

    return Track(
        title=title,
        artists=artists,
        album=album,
        duration_ms=duration,
        spotify_id=spotify_id,
    )


def _read_csv_tracks(path: Path) -> list[Track]:
    tracks: list[Track] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            track = _track_from_row(row)
            if track:
                tracks.append(track)
    return tracks


def _playlist_name_from_filename(path: Path) -> str:
    name = path.stem
    if name.lower() in ("liked songs", "saved tracks", "your library"):
        return "Liked Songs"
    return name


def _collect_csv_files(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() == ".zip":
        csv_files: list[Path] = []
        extract_dir = ensure_data_dir() / "exportify_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as zf:
            zf.extractall(extract_dir)
        csv_files.extend(sorted(extract_dir.rglob("*.csv")))
        return csv_files

    if source.is_file() and source.suffix.lower() == ".csv":
        return [source]

    if source.is_dir():
        return sorted(source.rglob("*.csv"))

    raise FileNotFoundError(f"No CSV or ZIP export found at: {source}")


def import_exportify(source: str | Path, output: str | Path | None = None) -> dict:
    """Build backup.json from Exportify CSV export(s)."""
    root = Path(source)
    if not root.exists():
        raise FileNotFoundError(f"Export path not found: {root}")

    liked_songs: list[Track] = []
    playlists: list[Playlist] = []
    artists: list[Artist] = []

    for csv_path in _collect_csv_files(root):
        tracks = _read_csv_tracks(csv_path)
        if not tracks:
            continue

        name = _playlist_name_from_filename(csv_path)
        is_liked = name.lower() == "liked songs" or "liked" in csv_path.name.lower()

        if is_liked:
            liked_songs.extend(tracks)
        else:
            playlists.append(
                Playlist(
                    name=name,
                    description="Imported from Exportify CSV",
                    tracks=tracks,
                )
            )

    data = {
        "liked_songs": [t.to_dict() for t in liked_songs],
        "playlists": [p.to_dict() for p in playlists],
        "artists": [a.to_dict() for a in artists],
    }

    out = Path(output) if output else BACKUP_FILE
    ensure_data_dir()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data
