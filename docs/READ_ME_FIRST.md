# READ_ME_FIRST

**Welcome!** This repo helps you transfer Spotify music to YouTube Music for free, locally, and privately.

![Animated transfer flow](assets/transfer-flow-animated.svg)

## Language options

- English: `docs/READ_ME_FIRST.md`
- Persian (Farsi): `docs/READ_ME_FIRST.fa.md`

## 60-second overview

- Export Spotify library using Exportify (browser)
- Import export into `spyt` backup
- Authenticate YouTube Music once
- Run migration and auto-refill missing tracks
- Review remaining unmatched songs

## Quick start (Windows)

1. Install Python from [python.org](https://www.python.org/downloads/) and enable **Add python.exe to PATH**
2. Run `scripts\install.bat`
3. Run `scripts\Start Spyt.bat`
4. Follow the guided steps in the terminal

If your country filters Spotify/Google, enable VPN first.

## Manual terminal flow

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env

python -m spyt export-spotify
python -m spyt import-exportify path\to\export.zip
python -m spyt setup-ytmusic
python -m spyt migrate-playlists --from-backup
```

## New here? Read this order

1. `docs/GETTING_STARTED.md` (simple beginner guide)
2. `README.md` (full docs + commands)
3. `docs/HANDOVER.md` (project status and architecture)

## Typical issues

- **YouTube auth says login failed:** run `python -m spyt setup-ytmusic` again with a fresh `youtubei/v1/browse` request
- **Some songs still missing:** run refill workflow and check `.spyt/unmatched.json`
- **Duplicate playlists in YTM:** keep fullest one, remove duplicates, then refill

## Repo structure

```text
spyt/
├── spyt/                # core Python package
├── scripts/             # Windows helpers
├── docs/                # docs for users and maintainers
└── .spyt/               # runtime data (gitignored)
```

If you are trying this project for the first time, start with `scripts\Start Spyt.bat`.
