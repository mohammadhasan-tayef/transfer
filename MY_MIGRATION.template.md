# My migration — personal notes

Fill this in **before you leave**. Then run `pack-for-home.bat` to copy everything into `home-pack\` for USB or cloud.

> **Do not upload this file or `home-pack\` to GitHub.** They contain your library data.

---

## Accounts

| Service | Email / username | Notes |
|---------|------------------|-------|
| Spotify | | |
| YouTube Music (Google) | | Same account you want the music on |
| VPN app | | e.g. Hiddify, Clash, v2rayN |

---

## VPN & network (home computer)

| Setting | Value |
|---------|-------|
| VPN on before starting? | Yes / No |
| Proxy port (if any) | e.g. `7890` |
| Worked without proxy on this PC? | |

---

## Library snapshot (this computer)

| Item | Count / status |
|------|----------------|
| Liked songs in backup | |
| Playlists kept (filtered) | |
| Exportify zip location | |
| Migration finished here? | Yes / No / Partial |

**Playlists selected for migration:**

```
(list playlist names)
```

**Notes from this run:**

```
(how far migration got, any errors, etc.)
```

---

## At home — quick steps

1. Install Python 3.10+ (Add to PATH)
2. Copy or clone the spyt project
3. Copy `home-pack\.spyt\*` into project `.spyt\`
4. Run `install.bat`
5. VPN on → `python -m spyt setup-ytmusic`
6. `python -m spyt migrate-all --from-backup`

See **README.md** for full details.
