# app/features/treasure/routers.py
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.templates import templates
from app.features.treasure.models import (
    Card,
    PileState,
    Player,
    Session,
    current_player,
    roll_d6,
    shuffle_bottom_random,
)
from app.features.treasure.scryfall import download_small, fetch_card_meta_by_name
from app.features.treasure.service import build_pile_from_source
from app.features.treasure.store import (
    create_session as db_create,
    get_asset,
    load_session as db_load,
    mutate_session as db_mutate,
    upsert_asset,
)

router = APIRouter()


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


async def _precache_card_images(sid: str, names: list[str]) -> None:
    name_meta: dict[str, dict] = {}
    for nm in dict.fromkeys([n for n in names if n]):
        meta = await run_in_threadpool(fetch_card_meta_by_name, nm)
        if not meta or not meta.get("oracle_id"):
            continue
        name_meta[nm] = meta

    uniq_by_oid = {m["oracle_id"]: m for m in name_meta.values()}
    for oid, meta in uniq_by_oid.items():
        existing = await get_asset(oid)
        if existing and existing.get("local_small_path"):
            continue
        local_path, etag, last_modified = await run_in_threadpool(
            download_small, oid, meta["small_url"]
        )
        await upsert_asset(oid, meta["name"], meta["small_url"], local_path, etag, last_modified)

    async def do_mutate(s: Session):
        for c in s.pile.cards:
            meta = name_meta.get(c.name)
            if not meta:
                continue
            c.oracle_id = meta["oracle_id"]
            asset = await get_asset(c.oracle_id)
            c.img = (asset.get("local_small_path") if asset else None) or meta["small_url"]
            c.scry = meta["scry_uri"]

    await db_mutate(sid, do_mutate)


async def _bg_precache_session(sid: str) -> None:
    s = await db_load(sid)
    if not s:
        return
    names = [c.name for c in s.pile.cards]
    total = len(set(names))

    async def set_progress(done_cnt: int):
        async def mut(s2: Session):
            s2.precache_total = total
            s2.precache_done = done_cnt

        await db_mutate(sid, mut)

    await set_progress(0)
    uniq = list(dict.fromkeys(names))
    for chunk_start in range(0, len(uniq), 25):
        chunk = uniq[chunk_start : chunk_start + 25]
        await _precache_card_images(sid, chunk)
        done = min(len(uniq), chunk_start + len(chunk))
        await set_progress(done)

    async def finish(s2: Session):
        s2.is_ready = True

    await db_mutate(sid, finish)


# ---------- Routes ----------


@router.get("")
async def treasure_home(request: Request):
    return templates.TemplateResponse("treasure/index.html", {"request": request})


@router.api_route("/create", methods=["GET", "POST"])
async def treasure_create(request: Request, background: BackgroundTasks):
    form = await request.form() if request.method == "POST" else {}

    def first(key: str, default: str | None = None) -> str | None:
        v = form.get(key) or request.query_params.get(key) or default
        if isinstance(v, str):
            v = v.strip()
        return v

    deck_url = first("deck_url")
    raw_list = first("raw_list")
    players = first("players")
    seed_raw = first("seed")

    seed: int | None = None
    if seed_raw not in (None, ""):
        try:
            seed = int(seed_raw)
        except ValueError:
            raise HTTPException(400, "seed must be an integer")

    cards = await run_in_threadpool(build_pile_from_source, deck_url, raw_list)
    if not cards:
        return templates.TemplateResponse(
            "treasure/index.html",
            {
                "request": request,
                "error": "Provide either a Moxfield deck URL or a raw card list.",
                "deck_url": deck_url or "",
                "raw_list": raw_list or "",
                "players": players or "",
            },
        )

    names = [n.strip() for n in (players or "").split(",") if n.strip()] or ["Player 1", "Player 2"]
    s = Session(players=[Player(name=n) for n in names], pile=PileState(cards=cards))
    if seed is not None:
        s.seed = seed
    s.is_ready = False
    s.precache_total = 0
    s.precache_done = 0
    await db_create(s)

    background.add_task(_bg_precache_session, s.id)

    return templates.TemplateResponse("treasure/precache.html", {"request": request, "sid": s.id})


@router.get("/precache_status")
async def precache_status(sid: str = Query(...)):
    s = await db_load(_norm_sid(sid))
    if not s:
        raise HTTPException(404, "session not found")
    return {
        "total": s.precache_total or 0,
        "done": s.precache_done or 0,
        "is_ready": bool(s.is_ready),
    }


@router.get("/open")
async def treasure_open(request: Request, sid: str = Query(..., description="Session code or URL")):
    code = _norm_sid(sid)
    s = await db_load(code)
    if not s:
        raise HTTPException(404, "session not found")
    if not s.is_ready:
        return templates.TemplateResponse(
            "treasure/precache.html", {"request": request, "sid": code}
        )
    return RedirectResponse(url=f"/treasure/{code}")


@router.get("/{sid}/state")
async def treasure_state(sid: str):
    s = await db_load(_norm_sid(sid))
    if not s:
        raise HTTPException(404, "session not found")
    return JSONResponse(s.model_dump())


@router.post("/{sid}/roll")
async def treasure_roll(sid: str, player_id: str | None = Form(None)):
    """
    Roll flow:
    - Roll 1–5: draw N from TOP; keep first; shuffle rest to BOTTOM; **do not advance**.
    - Roll 6: reveal TOP 3 (or fewer if deck small); wait for /choose; **do not advance**.
    """
    result_payload: dict[str, Any] = {}

    def do_roll(s: Session):
        _ensure_open(s)

        if getattr(s, "pending_choices", None):
            raise HTTPException(400, "awaiting choice from previous roll")

        p = (
            current_player(s)
            if not player_id
            else next((pl for pl in s.players if pl.id == player_id), None)
        )
        if not p:
            raise HTTPException(404, "player not found")
        if p.dug_this_turn:
            raise HTTPException(400, "already dug this turn")

        p.dug_this_turn = True
        p.digs_this_game += 1

        n = roll_d6()
        drawn: list[Card] = []

        if n == 6:
            cnt = min(3, len(s.pile.cards))
            for _ in range(cnt):
                drawn.append(s.pile.cards.pop(0))
            if drawn:
                s.pending_choices = list(drawn)
                s.pending_player_id = p.id
                _append_log(s, f"{p.name} rolled 6 — choose one of the top {len(drawn)}.")
                result_payload.update(
                    {
                        "mode": "choose",
                        "choices": [c.model_dump() for c in drawn],
                    }
                )
                return
            else:
                _append_log(s, f"{p.name} rolled 6 but the pile was empty.")
                result_payload.update({"mode": "auto", "revealed": []})
                return

        # 1–5
        for _ in range(n):
            if not s.pile.cards:
                break
            drawn.append(s.pile.cards.pop(0))

        if drawn:
            kept = drawn[0]
            p.gains.append(kept)
            rest = drawn[1:]
            if rest:
                shuffle_bottom_random(s, rest)
            _append_log(s, f"{p.name} dug {n} and found **{kept.name}**.")
            revealed_payload = [dict(kept.model_dump(), kept=True)]
            revealed_payload += [dict(c.model_dump(), kept=False) for c in rest]
            result_payload.update(
                {
                    "mode": "auto",
                    "received": kept.model_dump(),
                    "revealed": revealed_payload,
                }
            )
        else:
            _append_log(s, f"{p.name} dug {n} but found nothing.")
            result_payload.update({"mode": "auto", "revealed": []})

        # NOTE: Do NOT advance; pass must be explicit.

    await db_mutate(_norm_sid(sid), do_roll)
    s = await db_load(_norm_sid(sid))
    return JSONResponse({"ok": True, "state": s.model_dump() if s else {}, **result_payload})


@router.post("/{sid}/choose")
async def treasure_choose(sid: str, player_id: str | None = Form(None), card_id: str = Form(...)):
    result_payload: dict[str, Any] = {}

    def do_choose(s: Session):
        _ensure_open(s)

        choices = getattr(s, "pending_choices", None) or []
        if not choices:
            raise HTTPException(400, "no pending choices")

        p = (
            current_player(s)
            if not player_id
            else next((pl for pl in s.players if pl.id == player_id), None)
        )
        if not p:
            raise HTTPException(404, "player not found")
        if s.pending_player_id and s.pending_player_id != p.id:
            raise HTTPException(403, "not your choice")

        idx = next((i for i, c in enumerate(choices) if c.id == card_id), -1)
        if idx < 0:
            raise HTTPException(404, "card not in pending choices")

        chosen = choices[idx]
        p.gains.append(chosen)

        rest = [c for i, c in enumerate(choices) if i != idx]
        if rest:
            shuffle_bottom_random(s, rest)

        s.pending_choices = []
        s.pending_player_id = None

        _append_log(s, f"{p.name} chooses **{chosen.name}**.")
        result_payload.update(
            {
                "ok": True,
                "received": chosen.model_dump(),
                "revealed": [c.model_dump() for c in rest],
            }
        )
        # NOTE: Do NOT advance; pass must be explicit.

    await db_mutate(_norm_sid(sid), do_choose)
    s = await db_load(_norm_sid(sid))
    return JSONResponse({"ok": True, "state": s.model_dump() if s else {}, **result_payload})


@router.post("/{sid}/pass")
async def treasure_pass(sid: str):
    result_payload: dict[str, object] = {}

    def do_pass(s: Session):
        _ensure_open(s)
        p = current_player(s)
        if not p.dug_this_turn:
            _append_log(s, f"{p.name} passes without digging.")
        else:
            _append_log(s, f"{p.name} passes the turn.")
        _advance_turn(s)
        result_payload.update({"ok": True, "turn_advanced": True, "state": s.model_dump()})

    await db_mutate(_norm_sid(sid), do_pass)
    return JSONResponse(result_payload)


@router.get("/{sid}")
async def treasure_open_direct(request: Request, sid: str):
    code = _norm_sid(sid)
    s = await db_load(code)
    if not s:
        raise HTTPException(404, "session not found")
    if not s.is_ready:
        return templates.TemplateResponse(
            "treasure/precache.html", {"request": request, "sid": code}
        )
    return templates.TemplateResponse("treasure/session.html", {"request": request, "sid": code})


@router.post("/{sid}/end")
async def treasure_end(sid: str):
    sid = _norm_sid(sid)

    def do_close(s: Session):
        if getattr(s, "closed_at", None):
            return
        s.closed_at = datetime.now(UTC).isoformat()
        if getattr(s, "pending_choices", None):
            s.pending_choices = []
            s.pending_player_id = None
        _append_log(s, "Game ended.")

    await db_mutate(sid, do_close)
    s = await db_load(sid)
    if not s:
        raise HTTPException(404, "session not found")
    return JSONResponse({"ok": True, "state": s.model_dump()})
