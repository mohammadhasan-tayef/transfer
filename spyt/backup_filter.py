"""Filter ``backup.json`` to a subset of playlists before migration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from spyt.config import BACKUP_FILE, DATA_DIR, ensure_data_dir

KEEP_LIST_FILE = DATA_DIR / "keep_playlists.txt"


def _normalize(name: str) -> str:
    return name.strip().casefold()


def load_names_from_file(path: str | Path) -> list[str]:
    """Read playlist names from a text file (one per line, # = comment)."""
    text = Path(path).read_text(encoding="utf-8")
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Allow "12. chill (106 tracks)" format from list output
        if ". " in line and line[0].isdigit():
            line = line.split(". ", 1)[1]
        if " (" in line and line.endswith(" tracks)"):
            line = line.rsplit(" (", 1)[0]
        names.append(line.strip())
    return names


def export_keep_list_template(
    path: str | Path | None = None,
    *,
    backup_path: str | Path | None = None,
    include_liked: bool = False,
) -> Path:
    """
    Write all playlist names to a text file.
    Delete lines (or prefix with #) for playlists you do NOT want to migrate.
    """
    items = list_playlists(backup_path)
    out = Path(path) if path else KEEP_LIST_FILE
    ensure_data_dir()

    lines = [
        "# Playlists to migrate — one name per line.",
        "# Delete a line or prefix with # to skip that playlist.",
        "# No limit on how many you keep.",
        "",
    ]
    if include_liked:
        lines.extend([
            "# To also migrate Spotify liked songs, run filter-backup with --keep-liked",
            "",
        ])
    for item in items:
        lines.append(item["name"])

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def filter_backup(
    keep_playlists: list[str],
    *,
    keep_liked: bool = False,
    backup_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """Keep only named playlists (and optionally liked songs) in backup.json."""
    src = Path(backup_path) if backup_path else BACKUP_FILE
    if not src.is_file():
        raise FileNotFoundError(f"Backup not found: {src}")

    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    keep_set = {_normalize(n) for n in keep_playlists if n.strip()}
    if not keep_set:
        raise ValueError(
            "No playlist names to keep. Add names to the command or to your keep file."
        )

    all_playlists = data.get("playlists") or []
    kept = []
    removed = []
    for pl in all_playlists:
        name = pl.get("name") or ""
        if _normalize(name) in keep_set:
            kept.append(pl)
        else:
            removed.append(name)

    if len(kept) < len(keep_set):
        missing = keep_set - {_normalize(p.get("name", "")) for p in kept}
        for want in list(missing):
            for pl in all_playlists:
                name = pl.get("name") or ""
                norm = _normalize(name)
                if want in norm or norm in want:
                    if pl not in kept:
                        kept.append(pl)
                        missing.discard(want)

    still_missing = keep_set - {_normalize(p.get("name", "")) for p in kept}
    if still_missing:
        available = sorted({p.get("name", "") for p in all_playlists})
        raise ValueError(
            f"Playlist(s) not found: {', '.join(still_missing)}\n"
            f"Available ({len(available)}): " + ", ".join(available[:20])
            + ("..." if len(available) > 20 else "")
        )

    liked_count = len(data.get("liked_songs") or [])
    data["playlists"] = kept
    if not keep_liked:
        data["liked_songs"] = []
    data["artists"] = data.get("artists") or []

    dest = Path(output_path) if output_path else src
    ensure_data_dir()
    if dest.resolve() == src.resolve():
        shutil.copy2(src, src.with_suffix(".json.bak"))

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {
        "kept_playlists": [p.get("name") for p in kept],
        "removed_playlists": removed,
        "kept_count": len(kept),
        "removed_count": len(removed),
        "kept_liked_songs": keep_liked,
        "liked_songs_count": liked_count if keep_liked else 0,
        "output": str(dest),
    }


def filter_backup_from_file(
    file_path: str | Path,
    *,
    extra_names: list[str] | None = None,
    keep_liked: bool = False,
    backup_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    names = load_names_from_file(file_path)
    if extra_names:
        names.extend(extra_names)
    result = filter_backup(
        names,
        keep_liked=keep_liked,
        backup_path=backup_path,
        output_path=output_path,
    )
    result["from_file"] = str(file_path)
    return result


def list_playlists(backup_path: str | Path | None = None) -> list[dict]:
    """Return playlist names and track counts from a backup file."""
    src = Path(backup_path) if backup_path else BACKUP_FILE
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    return [
        {"name": p.get("name", ""), "tracks": len(p.get("tracks") or [])}
        for p in data.get("playlists") or []
    ]
