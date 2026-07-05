# spyt — Spotify to YouTube Music

Migrate your **liked songs**, **playlists**, and **followed artists** from Spotify to YouTube Music — completely free. No paid services, no subscriptions. Everything runs locally on your machine.

## New here? Start here

**No technical experience needed.**

1. Install [Python 3.10+](https://www.python.org/downloads/) (check **"Add python.exe to PATH"** on Windows)
2. Double-click **`install.bat`** once
3. Double-click **`Start Spyt.bat`** and follow the steps on screen

Full picture guide: **[GETTING_STARTED.md](GETTING_STARTED.md)**

The guided wizard opens websites for you, picks files with a normal file window, and explains each step in plain language.

---

| Spotify | YouTube Music |
|---------|---------------|
| Liked songs | Liked songs (thumbs up) |
| Playlists | New playlists with matched tracks |
| Followed artists | Subscribed artists |

Tracks are matched automatically using title, artist, and duration. Items that can't be matched are saved to `.spyt/unmatched.json` so you can add them manually later.

## Requirements

- Python 3.10+
- A YouTube Music account (free tier works for library management)
- Spotify access (via VPN if you're in a restricted region like Iran)
- Optional: Spotify Developer app — only if using `SPOTIFY_AUTH_MODE=custom`

## Quick start

### 1. Install

```bash
cd spyt
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Default auth mode is **`exportify`** — no Spotify Premium developer account needed.

If you're in Iran or another restricted region, turn on your VPN and uncomment proxy lines in `.env`:

```env
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

Use the port your VPN app shows (Clash, v2rayN, Hiddify, etc.). For SOCKS5: `pip install pysocks` and set `HTTPS_PROXY=socks5://127.0.0.1:1080`.

### 2b. Configure Spotify (optional — only for `custom` mode)

Skip this if `SPOTIFY_AUTH_MODE=exportify` (default).

### 3. Authorize both services (one-time each)

```bash
python -m spyt setup-spotify
python -m spyt setup-ytmusic
```

- **Spotify**: Opens your browser; log in and approve access.
- **YouTube Music**: Opens a browser flow; log in with the Google account tied to YouTube Music.

Check setup:

```bash
python -m spyt status
```

### 4. Migrate

**Recommended:** run a dry run first to see match rates without changing anything:

```bash
python -m spyt migrate-all --dry-run
```

Then run the real migration:

```bash
python -m spyt migrate-all
```

Or migrate one category at a time:

```bash
python -m spyt migrate-liked
python -m spyt migrate-playlists
python -m spyt migrate-artists
```

### 5. Optional backup

Export your Spotify library to JSON before migrating (useful if you want to re-run without hitting Spotify again):

```bash
python -m spyt backup
python -m spyt migrate-all --from-backup
```

## Commands

| Command | Description |
|---------|-------------|
| `start` (default) | Guided setup wizard for beginners |
| `setup-spotify` | Authorize Spotify |
| `setup-ytmusic` | Authorize YouTube Music |
| `status` | Show whether credentials are configured |
| `backup` | Export Spotify library to `.spyt/backup.json` |
| `migrate-liked` | Copy liked songs |
| `migrate-playlists` | Copy playlists |
| `migrate-artists` | Subscribe to followed artists |
| `migrate-all` | Run all three migrations |
| `--dry-run` | Match only, don't write to YouTube Music |
| `import-exportify` | Import Exportify CSV/ZIP into backup.json |
| `--from-backup` | Use local backup instead of Spotify API |

## How matching works

For each Spotify track, spyt searches YouTube Music and scores candidates by:

- Title similarity
- Artist similarity
- Duration closeness
- Preference for official song results over random videos

Only matches above a confidence threshold are imported. Expect ~90–98% match rates for mainstream music; obscure tracks, remixes, and region-locked content may not match.

## Cost

Everything is free:

- **Spotify API** — free for personal use via a developer app
- **ytmusicapi** — open-source, uses your own browser session
- **This tool** — runs locally; your credentials never leave your machine

## Iran / VPN / filtering

Spotify and Google are often blocked in Iran. Use a VPN for all steps below.

1. Turn on your VPN (system-wide or per-app).
2. Set proxy in `.env` if your VPN exposes a local HTTP/SOCKS port.
3. Re-authorize: `python -m spyt setup-spotify` and `python -m spyt setup-ytmusic`.

**If Spotify API still fails**, use the offline Exportify path:

1. With VPN on, open [exportify.app](https://exportify.app/) in your browser.
2. Log in to Spotify → click **Export All** → save the `.zip`.
3. Import locally (no Spotify API needed):

```bash
python -m spyt import-exportify path\to\export.zip
python -m spyt migrate-all --from-backup --dry-run
python -m spyt migrate-all --from-backup
```

## Troubleshooting

**"Active premium subscription required for the owner of the app"** — Your personal Spotify Developer app is in sandbox mode. Set `SPOTIFY_AUTH_MODE=exportify` in `.env` (default), delete `.spyt/.spotify_cache`, then run `python -m spyt setup-spotify` again.

**"Missing Spotify credentials"** — Only required for `SPOTIFY_AUTH_MODE=custom`. Use `exportify` mode instead.

**YouTube Music auth expired** — Re-run `python -m spyt setup-ytmusic`.

**Some songs didn't transfer** — Check `.spyt/unmatched.json`. You can search for those manually in YouTube Music.

**Duplicate playlists** — The tool creates new playlists each run. Delete duplicates in YouTube Music before re-running, or migrate categories individually.

**Rate limiting** — The tool pauses between requests automatically. For very large libraries (10k+ tracks), migration may take a while; that's normal.

## License

MIT — use freely.
