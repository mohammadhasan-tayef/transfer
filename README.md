# spyt

**Move your Spotify library to YouTube Music — free, local, and private.**

spyt copies your liked songs, playlists, and followed artists from Spotify to YouTube Music. It runs entirely on your computer. No paid migration services, no subscriptions, and your credentials never leave your machine.

Built for real-world constraints: restricted regions (VPN), no Spotify Premium developer access, and large libraries that take hours to transfer.

---

## What it does

| Spotify | → | YouTube Music |
|---------|---|---------------|
| Liked songs | → | Thumbs-up / liked songs |
| Playlists | → | New playlists with matched tracks |
| Followed artists | → | Subscribed artists |

Unmatched items are saved to `.spyt/unmatched.json` so you can add them manually later.

---

## Why spyt exists

Most migration tools assume you can use Spotify’s official API with a Premium-linked developer app. That often fails for:

- Users in **Iran and other filtered regions** (VPN required)
- **Free Spotify** accounts blocked by developer policy
- People who refuse to pay for **TuneMyMusic**, **Soundiiz**, etc.

spyt’s recommended path uses **[Exportify](https://exportify.app)** to export your library in the browser, then migrates locally with **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** — no Spotify API needed for the actual transfer.

---

## Requirements

| | |
|---|---|
| **Python** | 3.10 or newer |
| **Spotify** | Account + Exportify export (or API access if available) |
| **YouTube Music** | Free Google account |
| **VPN** | If Spotify or Google is blocked in your country |
| **Time** | ~2–3 seconds per track — large libraries take hours |

---

## Quick start (Windows)

The fastest way to run spyt on your own machine:

```
1. Install Python  →  https://www.python.org/downloads/
                     (check "Add python.exe to PATH")

2. install.bat     →  one-time setup

3. Start Spyt.bat  →  guided wizard (4 steps)
```

The wizard opens websites when needed, shows a file picker for your Exportify zip, walks you through YouTube Music login, and starts the migration.

**Taking work to another PC?** Fill in `MY_MIGRATION.md`, run `pack-for-home.bat`, and copy the `home-pack\` folder.

---

## Quick start (terminal)

```powershell
git clone <your-repo-url>
cd spyt
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# One-time: copy .env.example to .env (defaults work for Exportify path)
copy .env.example .env

# Recommended workflow (no Spotify API)
python -m spyt export-spotify          # opens Exportify
python -m spyt import-exportify path\to\export.zip
python -m spyt setup-ytmusic          # one-time browser auth
python -m spyt migrate-all --from-backup
```

Check everything is ready:

```powershell
python -m spyt status
```

Test matching without writing anything:

```powershell
python -m spyt migrate-all --from-backup --dry-run
```

---

## How it works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────────┐
│  Exportify  │ ──► │ backup.json  │ ──► │   Matcher   │ ──► │ YouTube Music  │
│  (browser)  │     │  (.spyt/)    │     │ fuzzy search│     │ likes + lists  │
└─────────────┘     └──────────────┘     └─────────────┘     └────────────────┘
```

1. **Import** — Exportify ZIP → `.spyt/backup.json`
2. **Filter** *(optional)* — keep only the playlists you want
3. **Auth** — save YouTube Music browser session (one-time)
4. **Match** — search YTM for each track; score by title, artist, duration
5. **Write** — thumbs-up liked songs; create playlists in batches

Matching weights: title 50% · artist 35% · duration 15% · minimum score 70.

---

## Commands

| Command | Description |
|---------|-------------|
| `start` | Guided wizard *(default when no args)* |
| `export-spotify` | Open Exportify in browser |
| `import-exportify <zip>` | Build `backup.json` from Exportify |
| `list-playlists` | Show playlists in backup |
| `export-keep-list` | Create editable playlist pick list |
| `filter-backup` | Trim backup to selected playlists |
| `setup-ytmusic` | One-time YouTube Music login |
| `setup-spotify` | One-time Spotify API login *(optional)* |
| `status` | Auth, proxy, and backup status |
| `migrate-all` | Migrate liked songs + playlists + artists |
| `migrate-liked` | Liked songs only |
| `migrate-playlists` | Playlists only |
| `migrate-artists` | Followed artists only |
| `--from-backup` | Use local `backup.json` instead of Spotify API |
| `--dry-run` | Match only — nothing written to YouTube Music |

---

## Playlist filtering

If your Exportify export has dozens of playlists and you only want some:

```powershell
python -m spyt export-keep-list
# Edit .spyt/keep_playlists.txt — delete or # lines you don't want

python -m spyt filter-backup --from-file .spyt/keep_playlists.txt --keep-liked
python -m spyt migrate-playlists --from-backup
```

---

## Iran / VPN

Spotify and Google are often blocked in Iran. For every step:

1. Turn on your VPN (system-wide or per-app).
2. Set `AUTO_PROXY=true` in `.env` (default) — spyt auto-detects common local proxy ports.
3. Or set manually:
   ```env
   HTTP_PROXY=http://127.0.0.1:7890
   HTTPS_PROXY=http://127.0.0.1:7890
   ```
4. Re-run `setup-ytmusic` if auth fails mid-migration.

---

## YouTube Music login

OAuth often returns HTTP 400. Use browser header auth instead:

1. Open [music.youtube.com](https://music.youtube.com) in **Chrome** (logged in).
2. Press **F12** → **Network** tab → filter: `browse`.
3. Click **Library** in YouTube Music.
4. Right-click a `youtubei/v1/browse` request → **Copy as cURL (cmd)**.
5. Run `python -m spyt setup-ytmusic` and paste (Ctrl+Z, Enter on Windows).

Use an API request — **not** the first page load (that has no cookies).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Spotify API Premium error | Use Exportify + `--from-backup` |
| YouTube auth expired | `python -m spyt setup-ytmusic` |
| Songs missing after run | Check `.spyt/unmatched.json` |
| Duplicate playlists | Delete extras in YTM before re-running |
| Migration very slow | Normal — rate-limited to ~0.35s per API call |
| Interrupted migration | Copy `backup.json` to new PC; re-auth YTM; run again |

---

## Project layout

```
spyt/
├── spyt/              # Python package
├── install.bat        # Windows one-time setup
├── Start Spyt.bat     # Windows guided wizard
├── pack-for-home.bat  # Bundle data for another computer
├── MY_MIGRATION.md    # Personal checklist (gitignored — fill in locally)
├── .spyt/             # Runtime data (gitignored)
│   ├── backup.json
│   ├── ytmusic_headers.json
│   └── unmatched.json
└── .env               # Config (gitignored)
```

---

## Privacy

- All processing is **local**.
- `.spyt/` and `.env` are **gitignored** — never commit them.
- Do not share `home-pack/` or `MY_MIGRATION.md` publicly.

---

## License

MIT — use freely.
