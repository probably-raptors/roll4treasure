# app/treasure/service.py
from __future__ import annotations
from typing import List, Any, Iterable, Optional
from uuid import uuid4
import os, re, requests

from .models import Card

UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

def _extract_deck_id(deck_url: str) -> str:
    """
    Accept either a full moxfield URL or a bare publicId (alnum).
    Examples:
      https://www.moxfield.com/decks/RXUTPR2uZk2guUuFICDhYg  -> RXUTPR2uZk2guUuFICDhYg
      RXUTPR2uZk2guUuFICDhYg                                -> RXUTPR2uZk2guUuFICDhYg
    """
    s = (deck_url or "").strip()
    m = re.search(r"/decks/([A-Za-z0-9]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", s):
        return s
    raise RuntimeError("Could not extract deck id from Moxfield URL or id.")

def _intish(x: Any, default: int = 1) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _is_tokenish(obj: dict) -> bool:
    """
    Heuristics to identify token/non-main entries present in deck payloads.
    We skip these explicitly.
    """
    # Common flags/fields seen on token-like entries
    if obj.get("is_token") or obj.get("token"):
        return True
    card = obj.get("card")
    if isinstance(card, dict):
        layout = (card.get("layout") or "").lower()
        if layout == "token":
            return True
        # Some payloads tag tokens by type line
        tline = (card.get("type_line") or "").lower()
        if "token" in tline:
            return True
    # Boards we don't want
    board = (obj.get("board") or "").lower()
    if board and board not in ("mainboard", "main"):
        return True
    return False

def _collect_from_entries(entries: Iterable[dict]) -> List[str]:
    names: List[str] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if _is_tokenish(e):
            continue
        name = None
        qty = _intish(e.get("quantity") or e.get("count") or e.get("qty"), 1)
        if "card" in e and isinstance(e["card"], dict) and "name" in e["card"]:
            name = e["card"]["name"]
        elif "name" in e:
            name = e["name"]
        if name:
            names.extend([name] * max(1, qty))
    return names

def fetch_moxfield_list(deck_url: str) -> List[str]:
    """
    Fetch the deck JSON and return ONLY the main deck (mainboard) card names,
    repeating by quantity. Tokens, sideboards, maybeboard, commanders, etc. are ignored.
    """
    deck_id = _extract_deck_id(deck_url)
    api_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"

    cookie = os.getenv("MOXFIELD_COOKIE", "").strip()
    if not cookie:
        raise RuntimeError("MOXFIELD_COOKIE is not set in environment.")

    headers = {
        "User-Agent": UA_HEADERS["User-Agent"],
        "Accept": UA_HEADERS["Accept"],
        "Origin": "https://www.moxfield.com",
        "Referer": f"https://www.moxfield.com/decks/{deck_id}",
        "Cookie": cookie,
    }

    r = requests.get(api_url, headers=headers, timeout=20)
    print(f"[moxfield] GET {api_url} -> {r.status_code}, body_len={len(r.text)}")
    if r.status_code != 200:
        raise RuntimeError(f"Moxfield fetch failed: {r.status_code} {r.text[:200]}")

    data = r.json()

    # --- Prefer the explicit boards/mainboard path (v3 shape) ---
    try:
        boards = data.get("boards") or {}
        # Common keys that might denote the "mainboard"
        main = (
            boards.get("mainboard")
            or boards.get("mainBoard")
            or boards.get("main")
        )
        if isinstance(main, dict):
            # Some payloads have `cards` as dict(id->entry) or list
            cards = main.get("cards") or main.get("entries") or main.get("list") or main
            if isinstance(cards, dict):
                entries = list(cards.values())
            elif isinstance(cards, list):
                entries = cards
            else:
                entries = []
            names = _collect_from_entries(entries)
            if names:
                print(f"[treasure] mainboard extracted via boards: {len(names)} names")
                return names
    except Exception as e:
        print(f"[treasure] boards parse fallback: {e!r}")

    # --- Fallback: guarded recursive walk, capturing only when board is mainboard ---
    names: List[str] = []

    def walk(node: Any, board_ctx: Optional[str] = None) -> None:
        if isinstance(node, dict):
            # Update board context if this node specifies it
            b = node.get("board")
            if isinstance(b, str) and b:
                board_ctx = b.lower()

            # Capture entries only when we are under mainboard
            if (board_ctx in ("mainboard", "main")) and not _is_tokenish(node):
                if "card" in node and isinstance(node["card"], dict) and "name" in node["card"]:
                    qty = _intish(node.get("quantity") or node.get("count") or node.get("qty"), 1)
                    names.extend([node["card"]["name"]] * max(1, qty))
                elif "name" in node and any(k in node for k in ("type", "type_line", "set", "setCode", "collector_number")):
                    qty = _intish(node.get("quantity") or node.get("count") or node.get("qty"), 1)
                    names.extend([str(node["name"])] * max(1, qty))

            for v in node.values():
                walk(v, board_ctx)

        elif isinstance(node, list):
            for v in node:
                walk(v, board_ctx)

    walk(data)

    print(f"[treasure] mainboard extracted via fallback walker: {len(names)} names")
    return names

def parse_raw_list(raw: str) -> List[str]:
    """
    Accepts the plain text export (one card per line, optionally 'N x Name').
    Returns a flat list of names, repeated by quantity.
    """
    out: List[str] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(?i)^\s*(\d+)\s*x?\s+(.+)$", line)
        if m:
            qty = _intish(m.group(1), 1)
            name = m.group(2).strip()
            out.extend([name] * max(1, qty))
        else:
            out.append(line)
    return out

def choose_tag(name: str) -> str:
    n = name.lower()
    if "curse" in n:
        return "curse"
    if any(k in n for k in ("signet", "talisman", "sol ring", "mind stone", "arcane signet", "fellwar stone")):
        return "rock"
    return "utility"

def normalize_to_cards(names: List[str]) -> List[Card]:
    return [Card(id=uuid4().hex, name=n, tag=choose_tag(n)) for n in names]

def build_pile_from_source(deck_url: str | None, raw_list: str | None) -> List[Card]:
    """
    Try Moxfield first (if we have a URL), else parse a pasted list.
    Only import *main deck* (mainboard) cards from Moxfield.
    """
    names: List[str] = []
    if deck_url:
        names = fetch_moxfield_list(deck_url)
        print(f"[treasure] build_pile_from_source: got {len(names)} names before normalization")
    elif raw_list:
        names = parse_raw_list(raw_list)
        print(f"[treasure] build_pile_from_source: got {len(names)} names from raw list")
    else:
        return []

    cards = normalize_to_cards(names)
    print(f"[treasure] final cards count (mainboard only): {len(cards)}")
    return cards
