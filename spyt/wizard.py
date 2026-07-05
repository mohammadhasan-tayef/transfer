"""Interactive setup wizard for non-technical users.

Walks through Exportify import, YouTube Music login, and migration using
plain language, Enter-to-continue prompts, and optional file-picker dialogs.
"""

from __future__ import annotations

import json
import shutil
import sys
import webbrowser
from pathlib import Path

from spyt.config import BACKUP_FILE, ENV_FILE, UNMATCHED_FILE, ensure_data_dir
from spyt.exportify_import import import_exportify
from spyt.migrate import migrate_all
from spyt.ytmusic_client import setup_ytmusic_auth, ytmusic_auth_exists


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def _pause(message: str = "Press Enter to continue...") -> None:
    try:
        input(f"\n{message}")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(130)


def _yes_no(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            answer = input(f"{question} [{hint}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(130)
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        _safe_print("Please type y or n.")


def _choose(question: str, options: list[str]) -> int:
    _safe_print()
    _safe_print(question)
    for i, label in enumerate(options, 1):
        _safe_print(f"  {i}. {label}")
    while True:
        try:
            raw = input(f"Choose 1-{len(options)}: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(130)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        _safe_print(f"Please enter a number from 1 to {len(options)}.")


def _pick_file(title: str) -> Path | None:
    """Open a file picker when possible; otherwise ask for a path."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("Exportify zip", "*.zip"), ("All files", "*.*")],
        )
        root.destroy()
        if path:
            return Path(path)
    except Exception:
        pass

    _safe_print()
    _safe_print("A file picker could not open. Type the full path to your file instead.")
    _safe_print('Example: C:\\Users\\YourName\\Downloads\\exportify.zip')
    try:
        typed = input("File path: ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(130)
    if not typed:
        return None
    return Path(typed)


def _ensure_env_file() -> None:
    """Create a minimal .env on first run so users never edit it manually."""
    if ENV_FILE.is_file():
        return
    example = ENV_FILE.parent / ".env.example"
    if example.is_file():
        shutil.copy(example, ENV_FILE)
        _safe_print(f"Created {ENV_FILE.name} with default settings (no editing needed).")
        return
    ENV_FILE.write_text("AUTO_PROXY=true\n", encoding="utf-8")
    _safe_print(f"Created {ENV_FILE.name} with default settings.")


def _banner() -> None:
    _safe_print()
    _safe_print("=" * 60)
    _safe_print("  SPYT - Move your Spotify music to YouTube Music")
    _safe_print("  Free. Runs on your computer. Your passwords stay private.")
    _safe_print("=" * 60)
    _safe_print()


def _step_exportify() -> None:
    _safe_print("-" * 60)
    _safe_print("STEP 1 of 4: Download your Spotify music list")
    _safe_print("-" * 60)
    _safe_print()
    _safe_print("We use a free website called Exportify to copy your Spotify library.")
    _safe_print("You will log in to Spotify in your web browser (like normal).")
    _safe_print()
    _safe_print("If Spotify is blocked in your country, turn on your VPN first.")
    _safe_print()
    if _yes_no("Open Exportify in your browser now?", default=True):
        webbrowser.open("https://exportify.app")
        _safe_print()
        _safe_print("In the browser:")
        _safe_print("  1. Click Get Started")
        _safe_print("  2. Log in to Spotify and agree")
        _safe_print("  3. Click Export All")
        _safe_print("  4. Save the .zip file (usually in your Downloads folder)")
    _pause("When the .zip file is saved on your computer, press Enter...")


def _step_import() -> bool:
    _safe_print()
    _safe_print("-" * 60)
    _safe_print("STEP 2 of 4: Import your Spotify export")
    _safe_print("-" * 60)
    _safe_print()
    _safe_print("A file window will open. Select the .zip file you just downloaded.")
    _pause("Press Enter to open the file picker...")

    path = _pick_file("Select your Exportify .zip file")
    if path is None:
        _safe_print("No file selected.")
        return False
    if not path.is_file():
        _safe_print(f"File not found: {path}")
        return False

    _safe_print(f"Importing {path.name} ... (this may take a minute)")
    data = import_exportify(str(path))
    liked = len(data.get("liked_songs") or [])
    playlists = len(data.get("playlists") or [])
    _safe_print()
    _safe_print("Import complete!")
    _safe_print(f"  Liked songs: {liked}")
    _safe_print(f"  Playlists:   {playlists}")
    return True


def _step_ytmusic() -> bool:
    _safe_print()
    _safe_print("-" * 60)
    _safe_print("STEP 3 of 4: Connect YouTube Music")
    _safe_print("-" * 60)
    _safe_print()
    _safe_print("YouTube Music needs a one-time login so we can add your songs.")
    _safe_print("This step uses Chrome and looks technical, but just follow the lines.")
    _safe_print()

    if ytmusic_auth_exists():
        if not _yes_no("YouTube Music is already connected. Connect again?", default=False):
            return True

    if _yes_no("Open music.youtube.com in your browser now?", default=True):
        webbrowser.open("https://music.youtube.com")

    _safe_print()
    _safe_print("Do this in Chrome (while logged in to YouTube Music):")
    _safe_print()
    _safe_print("  1. Press F12 on your keyboard (opens Developer Tools)")
    _safe_print("  2. Click the Network tab at the top")
    _safe_print("  3. In the filter box, type: browse")
    _safe_print("  4. Click Library on the left side of YouTube Music")
    _safe_print("  5. In the list, find a line that says youtubei/v1/browse")
    _safe_print("  6. Right-click that line -> Copy -> Copy as cURL (cmd)")
    _safe_print("  7. Come back here and paste it (then press Ctrl+Z, Enter on Windows)")
    _safe_print()
    _pause("Press Enter when you are ready to paste...")

    try:
        setup_ytmusic_auth()
    except Exception as exc:
        _safe_print()
        _safe_print(f"Connection failed: {exc}")
        _safe_print()
        if _yes_no("Try again?", default=True):
            return _step_ytmusic()
        return False

    _safe_print()
    _safe_print("YouTube Music connected successfully!")
    return True


def _backup_summary() -> tuple[int, int]:
    if not BACKUP_FILE.is_file():
        return 0, 0
    with open(BACKUP_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return len(data.get("liked_songs") or []), len(data.get("playlists") or [])


def _step_migrate() -> int:
    _safe_print()
    _safe_print("-" * 60)
    _safe_print("STEP 4 of 4: Copy music to YouTube Music")
    _safe_print("-" * 60)
    _safe_print()

    liked, playlists = _backup_summary()
    if liked == 0 and playlists == 0:
        _safe_print("Nothing to migrate yet. Complete steps 1-2 first.")
        return 1

    _safe_print(f"Ready to copy:")
    _safe_print(f"  {liked} liked songs")
    _safe_print(f"  {playlists} playlists")
    _safe_print()
    _safe_print("This takes a long time for large libraries (hours is normal).")
    _safe_print("You can leave this window open. Do not close it until it says Done.")
    _safe_print()

    choice = _choose(
        "What would you like to do?",
        [
            "Start copying everything now (recommended)",
            "Test first (match songs but do not add them yet)",
            "Skip for now - I will run this later",
        ],
    )

    if choice == 2:
        _safe_print()
        _safe_print("Skipped. To copy later, double-click Start Spyt.bat again")
        _safe_print("or run: python -m spyt migrate-all --from-backup")
        return 0

    dry_run = choice == 1
    if dry_run:
        _safe_print()
        _safe_print("TEST MODE - nothing will be added to YouTube Music yet.")
    else:
        if not _yes_no("Start copying to YouTube Music now?", default=True):
            return 0

    _safe_print()
    result = migrate_all(dry_run=dry_run, use_backup=True)
    _safe_print()
    _safe_print("=" * 60)
    if dry_run:
        _safe_print("  Test complete!")
    else:
        _safe_print("  Done!")
    _safe_print("=" * 60)

    liked_result = result.get("liked_songs") or {}
    _safe_print(
        f"  Liked songs: matched {liked_result.get('matched', 0)}, "
        f"not found {liked_result.get('unmatched', 0)}"
    )
    playlists_result = result.get("playlists") or {}
    playlist_count = len(playlists_result.get("playlists") or [])
    _safe_print(f"  Playlists:   {playlist_count} processed")

    if UNMATCHED_FILE.is_file() and not dry_run:
        _safe_print()
        _safe_print(f"Some songs could not be matched automatically.")
        _safe_print(f"They are listed in: {UNMATCHED_FILE}")
        _safe_print("You can search for those manually in the YouTube Music app.")

    if dry_run and _yes_no("Test looked good - start the real copy now?", default=True):
        _safe_print()
        migrate_all(dry_run=False, use_backup=True)
        _safe_print()
        _safe_print("Migration complete!")

    return 0


def run_wizard() -> int:
    """Run the full guided setup. Returns a process exit code."""
    _banner()
    _ensure_env_file()
    ensure_data_dir()

    _safe_print("This wizard will guide you through 4 steps:")
    _safe_print("  1. Download your Spotify library (website)")
    _safe_print("  2. Import the download file")
    _safe_print("  3. Connect YouTube Music (one-time)")
    _safe_print("  4. Copy everything over")
    _safe_print()
    _safe_print("Estimated time: 15 minutes setup, plus hours for large libraries.")
    _safe_print()

    if BACKUP_FILE.is_file():
        liked, playlists = _backup_summary()
        _safe_print(f"You already have a backup ({liked} songs, {playlists} playlists).")
        choice = _choose(
            "What would you like to do?",
            [
                "Continue from where I left off (skip re-import if possible)",
                "Start over from step 1 (new Exportify download)",
            ],
        )
        if choice == 0:
            if not ytmusic_auth_exists():
                if not _step_ytmusic():
                    return 1
            return _step_migrate()
        # choice == 1: full wizard from Exportify download

    _step_exportify()

    if not _step_import():
        if not _yes_no("Import failed. Try picking the file again?", default=True):
            return 1
        if not _step_import():
            _safe_print("Could not import. Ask for help and mention this step.")
            _pause()
            return 1

    if not _step_ytmusic():
        _safe_print("YouTube Music is required to copy your library.")
        _pause()
        return 1

    return _step_migrate()
