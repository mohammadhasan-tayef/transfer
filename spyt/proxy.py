"""Automatic VPN/proxy detection for restricted regions (e.g. Iran)."""

from __future__ import annotations

import json
import os
import socket
import sys
from urllib.request import getproxies

import requests

from spyt.config import DATA_DIR, ensure_data_dir, load_config

PROXY_CACHE_FILE = DATA_DIR / "proxy.json"
PROBE_URLS = (
    "https://www.google.com/generate_204",
    "https://open.spotify.com",
    "https://music.youtube.com",
)
PROBE_TIMEOUT = 4

# Common local proxy ports (Clash, v2rayN, Hiddify, Nekoray, etc.)
COMMON_HTTP_PROXIES = [
    "http://127.0.0.1:7890",
    "http://127.0.0.1:7897",
    "http://127.0.0.1:10808",
    "http://127.0.0.1:10809",
    "http://127.0.0.1:20171",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8888",
    "http://127.0.0.1:6152",
    "http://localhost:7890",
]

COMMON_SOCKS_PROXIES = [
    "socks5://127.0.0.1:1080",
    "socks5://127.0.0.1:10808",
    "socks5h://127.0.0.1:1080",
]

_configured = False
_active_proxy: dict[str, str] = {}
_proxy_source = "none"


def _auto_proxy_enabled() -> bool:
    load_config()
    value = os.getenv("AUTO_PROXY", "true").strip().lower()
    return value not in ("0", "false", "no", "off")


def _explicit_proxy_from_env() -> dict[str, str]:
    load_config()
    http = (os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "").strip()
    https = (os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or http).strip()
    if not http and not https:
        return {}
    return {"http": http or https, "https": https or http}


def _windows_system_proxy() -> dict[str, str]:
    if sys.platform != "win32":
        return {}

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return {}
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return {}

    if not server:
        return {}

    # Formats: "host:port" or "http=host:port;https=host:port"
    if "=" in server:
        parts: dict[str, str] = {}
        for piece in server.split(";"):
            if "=" in piece:
                scheme, addr = piece.split("=", 1)
                parts[scheme.strip()] = addr.strip()
        http = parts.get("http", "")
        https = parts.get("https", http)
    else:
        http = https = server

    def _normalize(addr: str) -> str:
        if not addr:
            return ""
        if addr.startswith(("http://", "https://", "socks")):
            return addr
        return f"http://{addr}"

    http_url = _normalize(http)
    https_url = _normalize(https)
    if not http_url and not https_url:
        return {}
    return {"http": http_url or https_url, "https": https_url or http_url}


def _urllib_proxies() -> dict[str, str]:
    proxies = getproxies()
    http = proxies.get("http") or ""
    https = proxies.get("https") or http
    if not http and not https:
        return {}
    return {"http": http, "https": https}


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_proxy(proxy_url: str) -> bool:
    proxies = {"http": proxy_url, "https": proxy_url}
    for url in PROBE_URLS:
        try:
            response = requests.get(
                url,
                proxies=proxies,
                timeout=PROBE_TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _direct_connection_works() -> bool:
    for url in PROBE_URLS:
        try:
            response = requests.get(url, timeout=PROBE_TIMEOUT, allow_redirects=True)
            if response.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _load_cached_proxy() -> dict[str, str]:
    if not PROXY_CACHE_FILE.is_file():
        return {}
    try:
        with open(PROXY_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        url = data.get("url", "")
        if url and _probe_proxy(url):
            return {"http": url, "https": url}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_cached_proxy(url: str, source: str) -> None:
    ensure_data_dir()
    with open(PROXY_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "source": source}, f, indent=2)


def _scan_local_proxies() -> dict[str, str]:
    candidates = COMMON_HTTP_PROXIES + COMMON_SOCKS_PROXIES
    # Quick port pre-check for 127.0.0.1 candidates to speed up scanning
    prioritized: list[str] = []
    rest: list[str] = []
    for url in candidates:
        host = "127.0.0.1"
        port = None
        if "://" in url:
            _, remainder = url.split("://", 1)
            if ":" in remainder:
                host_part, port_part = remainder.rsplit(":", 1)
                host = host_part or host
                try:
                    port = int(port_part.split("/")[0])
                except ValueError:
                    port = None
        if port and host in ("127.0.0.1", "localhost") and not _port_open(host, port):
            continue
        (prioritized if port else rest).append(url)

    for url in prioritized + rest:
        if _probe_proxy(url):
            return {"http": url, "https": url}
    return {}


def detect_proxy(*, force: bool = False) -> dict[str, str]:
    """Find a working proxy without user configuration."""
    global _active_proxy, _proxy_source

    if _active_proxy and not force:
        return _active_proxy

    if not _auto_proxy_enabled():
        _active_proxy = _explicit_proxy_from_env()
        _proxy_source = "env" if _active_proxy else "disabled"
        return _active_proxy

    explicit = _explicit_proxy_from_env()
    if explicit:
        if _probe_proxy(explicit["https"]):
            _active_proxy = explicit
            _proxy_source = "env"
            _save_cached_proxy(explicit["https"], "env")
            return _active_proxy

    if not force:
        cached = _load_cached_proxy()
        if cached:
            _active_proxy = cached
            _proxy_source = "cache"
            return _active_proxy

    for name, finder in (
        ("system", _windows_system_proxy),
        ("urllib", _urllib_proxies),
    ):
        found = finder()
        if found and _probe_proxy(found.get("https", found.get("http", ""))):
            _active_proxy = found
            _proxy_source = name
            _save_cached_proxy(found["https"], name)
            return _active_proxy

    scanned = _scan_local_proxies()
    if scanned:
        _active_proxy = scanned
        _proxy_source = "scan"
        _save_cached_proxy(scanned["https"], "scan")
        return _active_proxy

    if _direct_connection_works():
        _active_proxy = {}
        _proxy_source = "direct"
        return _active_proxy

    _active_proxy = {}
    _proxy_source = "none"
    return _active_proxy


def ensure_proxy_configured(*, quiet: bool = False) -> dict[str, str]:
    """Detect proxy once per process and apply it to the environment."""
    global _configured
    proxies = detect_proxy()
    if proxies:
        http = proxies.get("http", "")
        https = proxies.get("https", http)
        os.environ["HTTP_PROXY"] = http
        os.environ["HTTPS_PROXY"] = https
        os.environ["http_proxy"] = http
        os.environ["https_proxy"] = https
        if not quiet:
            print(f"[spyt] Using proxy {https} ({_proxy_source}, auto-detected)")
    elif not quiet and _auto_proxy_enabled():
        if _proxy_source == "direct":
            print("[spyt] Direct connection works — no proxy needed")
        else:
            print(
                "[spyt] No proxy detected. Turn on your VPN app, then run again.\n"
                "       Or set HTTP_PROXY in .env manually."
            )
    _configured = True
    return proxies


def get_proxy_info() -> tuple[dict[str, str], str]:
    ensure_proxy_configured(quiet=True)
    return _active_proxy, _proxy_source


def get_proxies() -> dict[str, str]:
    ensure_proxy_configured(quiet=True)
    return dict(_active_proxy)
