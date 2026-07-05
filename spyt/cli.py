"""Command-line interface for the spyt migration tool.

Registers subcommands (setup, backup, filter, migrate) and wires them to
the underlying service modules. Proxy auto-detection runs once at startup.
"""
import argparse
import json
import sys
from pathlib import Path

from spyt import __version__
from spyt.config import (
    BACKUP_FILE,
    SPOTIFY_CACHE,
    UNMATCHED_FILE,
    ensure_data_dir,
    get_spotify_pkce_config,
)
from spyt.exportify_import import import_exportify
from spyt.backup_filter import (
    KEEP_LIST_FILE,
    export_keep_list_template,
    filter_backup,
    filter_backup_from_file,
    list_playlists,
)
from spyt.proxy import ensure_proxy_configured, get_proxy_info
from spyt.migrate import (
    export_backup,
    migrate_all,
    migrate_artists,
    migrate_liked_songs,
    migrate_playlists,
)
from spyt.spotify_auth import SpotifyPremiumRequiredError
from spyt.spotify_client import create_spotify_client
from spyt.wizard import run_wizard
from spyt.ytmusic_client import setup_ytmusic_auth, ytmusic_auth_exists, ytmusic_auth_mode


def _print_json(data: dict) -> None:
    print(json.dumps(data, indent=2))


_EXPORTIFY_GUIDE = """
Your Spotify Developer app is blocked (Premium policy). This is normal — skip setup-spotify.

Use Exportify in your browser instead (VPN ON):

  1. Open https://exportify.app
  2. Click "Get Started" → log in to Spotify → Agree
  3. Click "Export All" → save the .zip file

Then in this terminal:

  python -m spyt import-exportify "C:\\Users\\PC2\\Downloads\\your-export.zip"
  python -m spyt migrate-all --from-backup --dry-run
  python -m spyt migrate-all --from-backup
"""


def cmd_setup_spotify(_: argparse.Namespace) -> int:
    print("NOTE: If your Spotify dev app is blocked, use Exportify instead (see export-spotify).")
    client_id, redirect_uri = get_spotify_pkce_config()
    print("Spotify login — make sure your VPN is ON (browser needs it too).")
    print(f"Redirect URI in .env: {redirect_uri}")
    print("This must match EXACTLY in Spotify Dashboard → your app → Settings → Redirect URIs.")
    print("Opening browser for Spotify authorization...")
    try:
        sp = create_spotify_client()
        user = sp.current_user()
        print(f"Connected as: {user.get('display_name') or user.get('id')}")
    except SpotifyPremiumRequiredError:
        print(_EXPORTIFY_GUIDE)
        return 1
    except Exception as exc:
        if "premium subscription required" in str(exc).lower():
            print(_EXPORTIFY_GUIDE)
            return 1
        raise
    return 0


def cmd_export_spotify(_: argparse.Namespace) -> int:
    import webbrowser

    print(_EXPORTIFY_GUIDE)
    print("Opening https://exportify.app in your browser...")
    webbrowser.open("https://exportify.app")
    return 0


def cmd_setup_ytmusic(_: argparse.Namespace) -> int:
    setup_ytmusic_auth()
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    ensure_data_dir()
    proxies, source = get_proxy_info()
    print(f"Proxy: {proxies.get('https', 'none')} ({source})")
    print(f"Spotify cache: {'yes' if SPOTIFY_CACHE.is_file() else 'no'}")
    mode = ytmusic_auth_mode()
    print(f"YouTube Music auth: {'yes (' + mode + ')' if mode else 'no'}")
    print(f"Backup file: {'yes' if BACKUP_FILE.is_file() else 'no'}")
    print(f"Unmatched log: {'yes' if UNMATCHED_FILE.is_file() else 'no'}")
    return 0


def cmd_import_exportify(args: argparse.Namespace) -> int:
    data = import_exportify(args.source, args.output)
    out = args.output or str(BACKUP_FILE)
    print(f"Imported Exportify export to {out}")
    print(
        f"  Liked songs: {len(data['liked_songs'])} | "
        f"Playlists: {len(data['playlists'])} | "
        f"Artists: {len(data['artists'])}"
    )
    print("Run migration with: python -m spyt migrate-all --from-backup")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    data = export_backup(args.output)
    out = args.output or str(BACKUP_FILE)
    print(f"Backup saved to {out}")
    print(
        f"  Liked songs: {len(data['liked_songs'])} | "
        f"Playlists: {len(data['playlists'])} | "
        f"Artists: {len(data['artists'])}"
    )
    return 0


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ))


def cmd_list_playlists(args: argparse.Namespace) -> int:
    items = list_playlists(args.backup)
    liked = 0
    backup = args.backup or str(BACKUP_FILE)
    if Path(backup).is_file():
        with open(backup, encoding="utf-8") as f:
            liked = len(json.load(f).get("liked_songs") or [])

    lines = [f"Liked songs in backup: {liked}", f"Playlists ({len(items)}):"]
    for i, item in enumerate(items, 1):
        lines.append(f"  {i:2}. {item['name']} ({item['tracks']} tracks)")

    if args.output:
        Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Playlist list saved to {args.output}")
    else:
        for line in lines:
            _safe_print(line)
    return 0


def cmd_export_keep_list(args: argparse.Namespace) -> int:
    out = export_keep_list_template(args.output, backup_path=args.backup)
    print(f"Edit this file — keep any number of playlists (delete or # the rest):")
    print(f"  {out}")
    print()
    print("Then run:")
    print(f"  python -m spyt filter-backup --from-file \"{out}\"")
    print(f"  python -m spyt migrate-playlists --from-backup")
    return 0


def cmd_filter_backup(args: argparse.Namespace) -> int:
    if args.from_file:
        result = filter_backup_from_file(
            args.from_file,
            extra_names=args.keep or [],
            keep_liked=args.keep_liked,
            backup_path=args.backup,
            output_path=args.output,
        )
    elif args.keep:
        result = filter_backup(
            args.keep,
            keep_liked=args.keep_liked,
            backup_path=args.backup,
            output_path=args.output,
        )
    else:
        print("Error: Provide playlist names or --from-file", file=sys.stderr)
        return 1

    _print_json(result)
    print(f"Kept {result['kept_count']} playlist(s), removed {result['removed_count']}.")
    print("Run: python -m spyt migrate-playlists --from-backup")
    return 0


def cmd_migrate_liked(args: argparse.Namespace) -> int:
    result = migrate_liked_songs(
        dry_run=args.dry_run,
        use_backup=args.from_backup,
        backup_path=args.backup,
    )
    _print_json(result)
    if result["unmatched"]:
        print(f"Unmatched tracks logged to {UNMATCHED_FILE}")
    return 0


def cmd_migrate_playlists(args: argparse.Namespace) -> int:
    result = migrate_playlists(
        dry_run=args.dry_run,
        use_backup=args.from_backup,
        backup_path=args.backup,
    )
    _print_json(result)
    return 0


def cmd_migrate_artists(args: argparse.Namespace) -> int:
    result = migrate_artists(
        dry_run=args.dry_run,
        use_backup=args.from_backup,
        backup_path=args.backup,
    )
    _print_json(result)
    if result["unmatched"]:
        print(f"Unmatched artists logged to {UNMATCHED_FILE}")
    return 0


def cmd_migrate_all(args: argparse.Namespace) -> int:
    result = migrate_all(
        dry_run=args.dry_run,
        use_backup=args.from_backup,
        backup_path=args.backup,
    )
    _print_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the root ``argparse`` parser and all subcommands."""
    parser = argparse.ArgumentParser(
        prog="spyt",
        description=(
            "Migrate your Spotify library (liked songs, playlists, followed artists) "
            "to YouTube Music — completely free."
        ),
    )
    parser.add_argument("--version", action="version", version=f"spyt {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "start",
        help="Guided setup wizard (recommended for beginners)",
    )
    p.set_defaults(func=lambda _: run_wizard())

    p = sub.add_parser("setup-spotify", help="Authorize Spotify (one-time)")
    p.set_defaults(func=cmd_setup_spotify)

    p = sub.add_parser(
        "export-spotify",
        help="Open Exportify to export library (use when Spotify API is blocked)",
    )
    p.set_defaults(func=cmd_export_spotify)

    p = sub.add_parser("setup-ytmusic", help="Authorize YouTube Music (one-time)")
    p.set_defaults(func=cmd_setup_ytmusic)

    p = sub.add_parser("status", help="Show setup status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("backup", help="Export Spotify library to JSON")
    p.add_argument("-o", "--output", help="Backup file path")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser(
        "import-exportify",
        help="Import Exportify CSV/ZIP export into backup.json (works offline / with VPN)",
    )
    p.add_argument("source", help="Path to Exportify .zip, .csv, or folder of CSVs")
    p.add_argument("-o", "--output", help="Output backup path (default: .spyt/backup.json)")
    p.set_defaults(func=cmd_import_exportify)

    p = sub.add_parser("list-playlists", help="List playlists in backup.json")
    p.add_argument("--backup", help="Backup file path")
    p.add_argument("-o", "--output", help="Save list to a UTF-8 text file")
    p.set_defaults(func=cmd_list_playlists)

    p = sub.add_parser(
        "export-keep-list",
        help="Create .spyt/keep_playlists.txt — edit it to pick any playlists you want",
    )
    p.add_argument(
        "-o", "--output",
        help=f"Output file (default: {KEEP_LIST_FILE})",
    )
    p.add_argument("--backup", help="Backup file path")
    p.set_defaults(func=cmd_export_keep_list)

    p = sub.add_parser(
        "filter-backup",
        help="Keep only selected playlists in backup.json (any number)",
    )
    p.add_argument(
        "keep",
        nargs="*",
        help="Playlist name(s) to keep (optional if using --from-file)",
    )
    p.add_argument(
        "-f", "--from-file",
        help="Text file with one playlist name per line (from export-keep-list)",
    )
    p.add_argument(
        "--keep-liked",
        action="store_true",
        help="Also keep liked songs (default: remove liked songs)",
    )
    p.add_argument("--backup", help="Input backup path")
    p.add_argument("-o", "--output", help="Output path (default: overwrite backup)")
    p.set_defaults(func=cmd_filter_backup)

    def add_migrate_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Search and match only; do not write to YouTube Music",
        )
        p.add_argument(
            "--from-backup",
            action="store_true",
            help="Use a local backup JSON instead of calling Spotify again",
        )
        p.add_argument("--backup", help="Path to backup JSON (default: .spyt/backup.json)")

    p = sub.add_parser("migrate-liked", help="Migrate liked songs")
    add_migrate_flags(p)
    p.set_defaults(func=cmd_migrate_liked)

    p = sub.add_parser("migrate-playlists", help="Migrate playlists")
    add_migrate_flags(p)
    p.set_defaults(func=cmd_migrate_playlists)

    p = sub.add_parser("migrate-artists", help="Migrate followed artists")
    add_migrate_flags(p)
    p.set_defaults(func=cmd_migrate_artists)

    p = sub.add_parser("migrate-all", help="Migrate liked songs, playlists, and artists")
    add_migrate_flags(p)
    p.set_defaults(func=cmd_migrate_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = success)."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv == ["start"]:
        ensure_proxy_configured()
        return run_wizard()

    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_proxy_configured()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
