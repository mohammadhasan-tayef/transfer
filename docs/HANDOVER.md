# spyt — Agent Handover Document

Last updated: 2026-07-05

## Project Overview

**spyt** is a free, local Python CLI that migrates a Spotify library to YouTube Music. It targets users who cannot rely on paid migration services or Spotify API access (e.g. Iran + VPN, developer apps blocked by Spotify Premium policy).

**Current status:** Core tool is complete and in active use. The user has imported an Exportify export, filtered it to 17 playlists + 2,411 liked songs, configured YouTube Music browser auth, and is running a **live** `migrate-all --from-backup` (was ~22% through liked songs when last checked — expect many hours total).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Spotify (optional) | [spotipy](https://github.com/spotipy-dev/spotipy) — PKCE/OAuth |
| Spotify data (recommended) | [Exportify](https://exportify.app) CSV/ZIP import |
| YouTube Music | [ytmusicapi](https://github.com/sigma67/ytmusicapi) — browser header auth |
| Matching | [thefuzz](https://github.com/seatgeek/thefuzz) fuzzy scoring |
| Other | python-dotenv, tqdm, PySocks, requests |

## Folder Structure

```
spyt/
├── spyt/                    # Python package
│   ├── __main__.py          # Entry: python -m spyt
│   ├── cli.py               # Argparse CLI and command handlers
│   ├── config.py            # Paths, .env, constants
│   ├── models.py            # Track, Playlist, Artist, MatchResult dataclasses
│   ├── migrate.py           # Migration orchestration
│   ├── matcher.py           # YTM search + fuzzy scoring
│   ├── spotify_client.py    # Spotify API fetch (liked/playlists/artists)
│   ├── spotify_auth.py      # PKCE/OAuth, Premium 403 handling
│   ├── ytmusic_client.py    # Browser auth, dual clients, library writes
│   ├── proxy.py             # Auto VPN/proxy detection
│   ├── exportify_import.py  # Import Exportify CSV/ZIP → backup.json
│   ├── backup_filter.py     # Trim backup to selected playlists
│   └── curl_headers.py      # Parse Chrome "Copy as cURL (cmd)"
├── .spyt/                   # Runtime data (gitignored)
│   ├── backup.json          # Current filtered library
│   ├── backup.json.bak      # Full pre-filter backup (72 playlists)
│   ├── ytmusic_headers.json # YouTube Music browser session
│   ├── keep_playlists.txt   # Editable playlist pick list
│   ├── unmatched.json       # Tracks/artists that failed matching
│   └── proxy.json           # Cached working proxy URL
├── .env                     # User credentials (DO NOT COMMIT)
├── .env.example
├── requirements.txt
├── pyproject.toml
├── README.md
└── HANDOVER.md              # This file
```

## What Has Been Completed

### Core features
- [x] CLI with subcommands for setup, import, filter, migrate, status
- [x] Spotify library fetch via API (when Premium/dev app allows)
- [x] **Exportify import** path (primary for this user — bypasses Spotify API)
- [x] **Backup-first workflow** (`backup.json` + `--from-backup`)
- [x] Playlist filtering (`export-keep-list`, `filter-backup`)
- [x] Fuzzy track matching (title 50% + artist 35% + duration 15% + song-type bonus; min score 70)
- [x] Migrate liked songs → YTM thumbs-up
- [x] Migrate playlists → new YTM playlists (batch add, 25 tracks/call)
- [x] Migrate followed artists → YTM subscriptions (empty for Exportify — no artist data)
- [x] Unmatched items logged to `.spyt/unmatched.json`
- [x] Dry-run mode (`--dry-run`)
- [x] Auto proxy detection (Windows system proxy, common VPN ports, cache)
- [x] YouTube Music **browser header auth** via Chrome cURL paste
- [x] Dual YTM clients: unauthenticated search vs authenticated library writes
- [x] Module-level and key function docstrings (Google-style / PEP 257)

### User-specific progress
- [x] Exportify zip imported
- [x] Backup filtered: **2,411 liked songs** + **17 playlists** (full backup preserved as `.bak`)
- [x] YTM auth configured (browser headers from `youtubei/v1/browse` POST)
- [x] Live migration started: `python -m spyt migrate-all --from-backup`

### Kept playlists (17)
`mamanesh_bishtar`, `gym`, `drake_house`, `drake_vibe`, `tentacion_vibe`, `travis_scott_vibe`, `love_in_other_words`, `skyrim_relaxing_ambience`, `rainy`, `frank_freak`, `joji•depression`, `daryakenar`, `highway_vibe`, `cry_`, `nf_chill_songs`, `ambient_relaxation`, `chill_az_fuck`

## CLI Reference

```bash
python -m spyt setup-ytmusic          # One-time YTM browser auth
python -m spyt import-exportify <zip> # Build backup.json from Exportify
python -m spyt list-playlists         # Show playlists in backup
python -m spyt export-keep-list       # Create editable keep list
python -m spyt filter-backup --from-file .spyt/keep_playlists.txt --keep-liked
python -m spyt status                 # Auth + proxy status
python -m spyt migrate-all --from-backup --dry-run
python -m spyt migrate-all --from-backup
python -m spyt migrate-liked --from-backup
python -m spyt migrate-playlists --from-backup
```

## Architectural Rules & Patterns

1. **Backup-first for restricted users**  
   Exportify → `import-exportify` → optional `filter-backup` → `migrate-* --from-backup`. Avoids Spotify API entirely.

2. **Dual YouTube Music clients**  
   - `create_ytmusic_search_client()` — no auth, used for search/matching  
   - `create_ytmusic_client()` — browser headers required for likes, playlists, subscriptions  

3. **Rate limiting**  
   `YTM_REQUEST_DELAY_SEC = 0.35` between all YTM API calls (in `matcher.py` and `migrate.py`).

4. **Matching pipeline**  
   Multiple search queries per track → score each result → accept if ≥ `MIN_MATCH_SCORE` (70). Early exit at score ≥ 90.

5. **Playlist migration**  
   Match all tracks first (dry-run path), then create playlist and batch-add video IDs.

6. **Proxy**  
   `ensure_proxy_configured()` runs once at CLI startup. Order: env vars → cache → Windows registry → urllib → port scan → direct.

7. **Error translation**  
   Spotify 403 Premium → `SpotifyPremiumRequiredError` with Exportify instructions.

8. **Data directory**  
   All runtime state under `.spyt/` (gitignored). Never commit `.env` or auth files.

## Known Issues & Workarounds

| Issue | Workaround |
|-------|------------|
| Spotify dev app requires Premium | Use Exportify + `--from-backup` |
| YTM OAuth returns HTTP 400 | Use `setup-ytmusic` with browser cURL headers |
| Chrome has no "Copy request headers" | Paste **Copy as cURL (cmd)** — parsed by `curl_headers.py` |
| Page-load request has no cookies | Copy `youtubei/v1/browse` POST, not document load |
| Exportify has no followed artists | `artists: []` in backup — artist step is a no-op |
| Migration is very slow | ~2.5 s/track; 2,411 liked + playlists = many hours |
| YTM session expiry | Re-run `setup-ytmusic` if library writes fail mid-migration |

## Next Steps & Pending Tasks

### Immediate (user)
1. **Let `migrate-all` finish** — do not interrupt unless errors appear.
2. **Check `.spyt/unmatched.json`** after completion; manually add stubborn tracks in YTM.
3. **Verify playlists** in YouTube Music Library after migration.

### If migration fails mid-run
1. Check terminal error (auth expiry, rate limit, network).
2. Re-auth: `python -m spyt setup-ytmusic`
3. Re-run migration commands (see improvement note below about resume).

### Future improvements (not implemented)
- [ ] **Resume / skip already-liked** — avoid re-processing thousands of tracks on retry
- [ ] **Progress checkpoint file** — save offset for interrupted runs
- [ ] Remove or fix dead YTM OAuth code path
- [ ] Windows console emoji-safe output
- [ ] Parallel search (careful with rate limits)
- [ ] README sync with actual `SPOTIFY_AUTH_MODE=pkce` default (README still mentions `exportify` mode name)

### Security note
User has pasted live cookies and API credentials in chat history. Recommend rotating Spotify/Google credentials and re-running `setup-ytmusic` after migration if concerned.

## Environment (`.env`)

Typical configuration for this user:

```env
SPOTIFY_AUTH_MODE=pkce
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://127.0.0.1:9090
AUTO_PROXY=true
```

Spotify credentials are unused when migrating from backup. YTM uses `.spyt/ytmusic_headers.json`, not OAuth env vars.

## For the Next Agent

**Goal:** Help user complete Spotify → YouTube Music migration with zero paid services.

**Start here:**
1. Read this file and `README.md`
2. Check migration status: terminal output or re-run `python -m spyt status`
3. Inspect `.spyt/backup.json` (filtered) and `.spyt/unmatched.json` (failures)
4. Do not commit `.env`, `.spyt/`, or credentials

**Key commands:**
```bash
cd d:\Mohammad-Hasan\spyt
.venv\Scripts\activate
python -m spyt status
python -m spyt migrate-all --from-backup   # if migration was interrupted
```

**Iran / VPN:** User needs VPN for browser and terminal. `AUTO_PROXY=true` handles most local proxy apps (Clash, v2rayN, Hiddify, etc.).
