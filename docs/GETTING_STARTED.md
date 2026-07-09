# Getting started (simple guide)

**spyt** copies your Spotify music to YouTube Music. It is free and runs on your computer.

You do **not** need to know programming. Follow the steps below.

---

## What you need

1. A **Windows** computer (Mac/Linux: see [README.md](../README.md))
2. **Python** installed ([download here](https://www.python.org/downloads/) — check **"Add python.exe to PATH"** during install)
3. A **Spotify** account
4. A **YouTube Music** account (free is fine)
5. **VPN** if Spotify or Google is blocked in your country (e.g. Iran)

---

## Easiest way (3 clicks)

1. **Download** this project folder to your computer
2. **Double-click** `scripts\install.bat` once (waits until it says "Setup complete")
3. **Double-click** `scripts\Start Spyt.bat` and follow the on-screen steps

The program will:

- Open websites when you need to log in
- Open a file picker so you can choose your Spotify export
- Walk you through YouTube Music login
- Copy your music (this can take **many hours** for large libraries — leave the window open)

---

## The 4 steps (what the wizard does)

### Step 1 — Download from Spotify

- The program opens [exportify.app](https://exportify.app)
- Log in to Spotify in your browser
- Click **Export All** and save the `.zip` file (usually in Downloads)

### Step 2 — Import

- A file window opens — select the `.zip` you saved
- Wait until it says "Import complete"

### Step 3 — Connect YouTube Music

This is the trickiest step. You only do it once.

1. Open [music.youtube.com](https://music.youtube.com) in **Chrome** and log in
2. Press **F12** on your keyboard
3. Click the **Network** tab
4. Type `browse` in the filter box
5. Click **Library** on the left in YouTube Music
6. Find a line named `youtubei/v1/browse`
7. Right-click it → **Copy** → **Copy as cURL (cmd)**
8. Go back to the spyt window, paste, then press **Ctrl+Z** and **Enter**

### Step 4 — Copy music

- Choose **Start copying everything now**
- Do not close the window until it finishes
- Songs that could not be matched are saved in `.spyt/unmatched.json` — add those manually in the YouTube Music app if you want

---

## If something goes wrong

| Problem | What to do |
|---------|------------|
| "Python is not installed" | Install Python from python.org, check "Add to PATH", run `scripts\install.bat` again |
| Spotify won't open | Turn on VPN, try Exportify again in the browser |
| YouTube login failed | Repeat Step 3 with a `browse` request (not the first page load) |
| Copy stopped halfway | Double-click `scripts\Start Spyt.bat` again and choose "Continue from where I left off" |
| Duplicate playlists | Delete extra playlists in YouTube Music before running again |

---

## For advanced users

See [README.md](README.md) for all commands, playlist filtering, dry-run mode, and proxy settings.

---

## Privacy

- Everything runs on **your** computer
- Your Spotify export and YouTube login stay in the `.spyt` folder on your machine
- Do not share the `.spyt` folder or `.env` file with anyone
