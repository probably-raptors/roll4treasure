# app/features/treasure/scryfall.py
from __future__ import annotations

import os

import requests

UA_HEADERS = {
    "User-Agent": "Roll4Treasure/1.0 (+https://example.com/contact)",
    "Accept": "application/json",
}

IMG_HEADERS = {
    "User-Agent": UA_HEADERS["User-Agent"],
    # prefer smallest modern types; Scryfall serves jpeg/webp/avif accordingly
    "Accept": "image/avif,image/webp,image/jpeg;q=0.8,*/*;q=0.5",
}


def _cache_dir() -> str:
    return os.getenv("IMAGE_CACHE_DIR", "/opt/r4t/img-cache").rstrip("/")


def ensure_cache_dir() -> str:
    d = _cache_dir()
    os.makedirs(d, exist_ok=True)
    return d


def fetch_card_meta_by_name(name: str) -> dict | None:
    """
    Scryfall 'named' endpoint. We want oracle_id + small image + scryfall_uri.
    """
    url = "https://api.scryfall.com/cards/named"
    r = requests.get(url, params={"exact": name}, headers=UA_HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    # single-faced only (per the user request); ignore special cases
    img = (data.get("image_uris") or {}).get("small")
    return {
        "name": data.get("name") or name,
        "oracle_id": data.get("oracle_id"),
        "small_url": img,
        "scry_uri": data.get("scryfall_uri"),
    }


def download_small(oracle_id: str, small_url: str) -> tuple[str, str | None, str | None]:
    """
    Download small image to cache dir and return (local_path, etag, last_modified).
    """
    ensure_cache_dir()
    r = requests.get(small_url, headers=IMG_HEADERS, timeout=30)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "image/jpeg").lower()
    ext = ".jpg"
    if "webp" in ctype:
        ext = ".webp"
    elif "avif" in ctype:
        ext = ".avif"
    fname = f"{oracle_id}{ext}"
    path = os.path.join(_cache_dir(), fname)
    with open(path, "wb") as f:
        f.write(r.content)
    return f"/img-cache/{fname}", r.headers.get("ETag"), r.headers.get("Last-Modified")
