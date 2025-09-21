# app/web/routes_treasure.py
from fastapi import APIRouter, Request, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool
from typing import Optional, Dict, List
import random, re, os

from app.treasure.models import (
    Session, Player, PileState, Card,
    current_player, shuffle_bottom_random, roll_d6,
)
from app.treasure.service import build_pile_from_source
from app.treasure.store import (
    create_session as db_create,
    load_session as db_load,
    mutate_session as db_mutate,
    get_asset, upsert_asset,
)
from app.treasure.scryfall import fetch_card_meta_by_name, download_small

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def _append_log(s: Session, line: str, cap: int = 500) -> None:
    s.log.append(line)
    if len(s.log) > cap:
        del s.log[: len(s.log) - cap]

def _advance_turn(s: Session) -> None:
    s.players[s.turn_idx].dug_this_turn = False
    s.turn_idx = (s.turn_idx + 1) % len(s.players)
    if s.turn_idx == 0:
        s.turn_num += 1

def _ensure_open(s: Session) -> None:
    if s.closed_at:
        raise HTTPException(status_code=423, detail="session closed")

def _norm_sid(raw: str) -> str:
    m = re.search(r"([0-9a-fA-F]{32})", (raw or ""))
    if not m:
        raise HTTPException(400, "Invalid session code.")
    return m.group(1).lower()

# ---------- Precache orchestration ----------

async def _bg_precache_session(sid: str):
    """
    Resolve names -> oracle_id & small image, download and store locally,
    update session cards with oracle_id/img/scry, track progress.
    """
    # 1) Load current session snapshot
    s = await db_load(sid)
    if not s:
        return

    names = [c.name for c in s.pile.cards]
    uniq_meta: Dict[str, Dict] = {}  # oracle_id -> meta
    name_meta: Dict[str, Dict] = {}  # name -> meta (for stamp onto every card)

    # 2) Resolve names (blocking requests -> threadpool)
    for nm in names:
        meta = await run_in_threadpool(fetch_card_meta_by_name, nm)
        if not meta or not meta.get("oracle_id"):
            # leave missing; UI can fall back later if truly unknown
            continue
        name_meta[nm] = meta
        uniq_meta.setdefault(meta["oracle_id"], meta)

    # 3) Download new assets (dedupe by oracle_id)
    total = len(uniq_meta)
    done = 0

    async def set_progress(done_cnt: int):
        async def mut(s2: Session):
            s2.precache_total = total
            s2.precache_done = done_cnt
        await db_mutate(sid, mut)

    await set_progress(0)

    for oid, meta in uniq_meta.items():
        # already cached?
        asset = await get_asset(oid)
        local_path = asset["local_small_path"] if asset else None
        if not local_path:
            if meta.get("small_url"):
                # download (blocking -> threadpool)
                local_path, etag, lastmod = await run_in_threadpool(download_small, oid, meta["small_url"])
                await upsert_asset(oid, meta["name"], meta["small_url"], local_path, etag, lastmod)
        done += 1
        await set_progress(done)

    # 4) Stamp every card in the session with oracle_id/img/scry (prefer local path)
    async def finalize(st: Session):
        st.precache_total = total
        st.precache_done = done
        st.precache_error = None
        for c in st.pile.cards:
            meta = name_meta.get(c.name)
            if not meta:
                continue
            c.oracle_id = meta["oracle_id"]
            # prefer local path if present
            asset = None
            if c.oracle_id:
                asset = await get_asset(c.oracle_id)
            c.img = (asset and asset.get("local_small_path")) or meta.get("small_url") or c.img
            c.scry = meta.get("scry_uri") or c.scry
        st.is_ready = True

    await db_mutate(sid, finalize)

# ---------- Routes ----------

@router.get("/treasure")
async def treasure_home(request: Request):
    sid = request.query_params.get("sid")
    if sid:
        code = _norm_sid(sid)
        return RedirectResponse(url=f"/treasure/open?sid={code}", status_code=307)
    return templates.TemplateResponse("treasure_index.html", {"request": request})

@router.api_route("/treasure/create", methods=["GET", "POST"])
async def treasure_create(request: Request, background: BackgroundTasks):
    form = await request.form() if request.method == "POST" else {}

    def first(key: str, default: Optional[str] = None) -> Optional[str]:
        v = form.get(key) or request.query_params.get(key) or default
        if isinstance(v, str): v = v.strip()
        return v

    deck_url = first("deck_url")
    raw_list = first("raw_list")
    players  = first("players")
    seed_raw = first("seed")

    seed: Optional[int] = None
    if seed_raw not in (None, ""):
        try: seed = int(seed_raw)
        except ValueError: raise HTTPException(400, detail="seed must be an integer if provided")

    try:
        cards = build_pile_from_source(deck_url, raw_list)
    except RuntimeError as e:
        return templates.TemplateResponse("treasure_index.html", {"request": request, "error": str(e)}, status_code=400)

    if seed is not None: random.seed(seed)
    random.shuffle(cards)

    names = [n.strip() for n in (players or "").split(",") if n.strip()] or ["Player 1", "Player 2"]
    s = Session(players=[Player(name=n) for n in names], pile=PileState(cards=cards))
    s.is_ready = False
    s.precache_total = 0
    s.precache_done = 0
    await db_create(s)

    # kick off background prefetch
    background.add_task(_bg_precache_session, s.id)

    # show progress page
    return templates.TemplateResponse("treasure_precache.html", {"request": request, "sid": s.id})

@router.get("/treasure/precache_status")
async def precache_status(sid: str = Query(...)):
    s = await db_load(sid)
    if not s:
        raise HTTPException(404, "session not found")
    return {
        "sid": sid,
        "is_ready": s.is_ready,
        "total": s.precache_total,
        "done": s.precache_done,
        "error": s.precache_error,
    }

@router.get("/treasure/open")
async def treasure_open(request: Request, sid: str = Query(..., description="Session code or URL")):
    code = _norm_sid(sid)
    s = await db_load(code)
    if not s:
        return templates.TemplateResponse("treasure_index.html", {"request": request, "error": "Session not found."}, status_code=404)
    if not s.is_ready:
        return templates.TemplateResponse("treasure_precache.html", {"request": request, "sid": code})
    return templates.TemplateResponse("treasure_session.html", {"request": request, "sid": code})

# API: state/roll/choose/pass (unchanged from your working version, gated by is_ready)

@router.get("/treasure/{sid}/state")
async def treasure_state(sid: str):
    s = await db_load(sid)
    if not s: raise HTTPException(404, "session not found")
    if not s.is_ready: raise HTTPException(409, "session not ready")
    return JSONResponse(s.model_dump())

@router.post("/treasure/{sid}/roll")
async def treasure_roll(sid: str, player_id: Optional[str] = Form(None)):
    result_payload = {}

    async def do_roll(s: Session):
        if not s.is_ready: raise HTTPException(409, "session not ready")
        _ensure_open(s)
        p = current_player(s)
        if player_id and p.id != player_id:
            _append_log(s, f"(note) ignoring player_id mismatch; it is {p.name}'s turn.")
        if p.dug_this_turn: raise HTTPException(400, "already dug this turn")

        cost = 1 + p.digs_this_game
        _append_log(s, f"{p.name} pays {cost} to dig.")
        roll = roll_d6()
        _append_log(s, f"{p.name} rolls a {roll}.")

        s.pile.revealed.clear()
        if roll in (1,2,3,4,5):
            n = min(roll, len(s.pile.cards))
            s.pile.revealed = s.pile.cards[:n]
            s.pile.cards    = s.pile.cards[n:]
            auto = s.pile.revealed[-1] if s.pile.revealed else None
            just_revealed = list(s.pile.revealed)
            to_bottom = s.pile.revealed[:-1]
            s.pile.revealed = []

            if auto:
                _append_log(s, f"→ {p.name} receives **{auto.name}**.")
                p.gains.append(auto)

            shuffle_bottom_random(s, to_bottom)
            p.digs_this_game += 1
            p.dug_this_turn = True
            _advance_turn(s)

            result_payload.update({
                "roll": roll, "mode": "auto",
                "received": auto.model_dump() if auto else None,
                "revealed": [c.model_dump() for c in just_revealed],
                "bottomed_count": len(to_bottom),
                "turn_advanced": True,
                "state": s.model_dump(),
            })
        else:
            n = min(3, len(s.pile.cards))
            s.pile.revealed = s.pile.cards[:n]
            s.pile.cards    = s.pile.cards[n:]
            result_payload.update({
                "roll": roll, "mode": "choose",
                "choices": [c.model_dump() for c in s.pile.revealed],
                "state": s.model_dump(),
            })

    await db_mutate(sid, do_roll)
    return JSONResponse(result_payload)

@router.post("/treasure/{sid}/choose")
async def treasure_choose(sid: str, player_id: Optional[str] = Form(None), card_id: str = Form(...)):
    result_payload = {}

    async def do_choose(s: Session):
        if not s.is_ready: raise HTTPException(409, "session not ready")
        _ensure_open(s)
        p = current_player(s)
        if player_id and p.id != player_id:
            _append_log(s, "(note) player_id mismatch on choose; using current player.")
        pick = next((c for c in s.pile.revealed if c.id == card_id), None)
        if not pick: raise HTTPException(400, "choice not in revealed")
        rest = [c for c in s.pile.revealed if c.id != card_id]
        s.pile.revealed.clear()

        _append_log(s, f"→ {p.name} chooses **{pick.name}**.")
        shuffle_bottom_random(s, rest)
        p.gains.append(pick)
        p.digs_this_game += 1
        p.dug_this_turn   = True
        _advance_turn(s)

        result_payload.update({"ok": True, "received": pick.model_dump(), "turn_advanced": True, "state": s.model_dump()})

    await db_mutate(sid, do_choose)
    return JSONResponse(result_payload)

@router.post("/treasure/{sid}/pass")
async def treasure_pass(sid: str):
    result_payload = {}

    def do_pass(s: Session):
        if not s.is_ready: raise HTTPException(409, "session not ready")
        _ensure_open(s)
        p = current_player(s)
        if s.pile.revealed:
            raise HTTPException(400, "cannot pass while a choice is pending")
        _append_log(s, f"{p.name} passes the turn.")
        _advance_turn(s)
        result_payload.update({"ok": True, "turn_advanced": True, "state": s.model_dump()})

    await db_mutate(sid, do_pass)
    return JSONResponse(result_payload)

@router.get("/treasure/{sid}")
async def treasure_open_direct(request: Request, sid: str):
    code = _norm_sid(sid)
    s = await db_load(code)
    if not s: raise HTTPException(404, "session not found")
    if not s.is_ready:
        return templates.TemplateResponse("treasure_precache.html", {"request": request, "sid": code})
    return templates.TemplateResponse("treasure_session.html", {"request": request, "sid": code})
