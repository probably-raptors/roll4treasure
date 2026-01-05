from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.templates import templates
from app.features.house.engine import simulate
from app.features.house.models import SimRequest

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def house_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "house/index.html",
        {
            "request": request,
            "result_json": None,
            "seed": "",
            "untapped_other_init": 0,
            "stop_at_100": False,
            "delney": False,
            "stop_treasures_ge": "",
            "stop_robots_ge": "",
            "stop_mana_ge": "",
        },
    )


def _build_req_from_params(params: dict[str, Any]) -> SimRequest:
    def _str(name: str, default: str | None = None) -> str | None:
        v = params.get(name, default)
        return None if v in ("", None) else str(v)

    def _int(name: str) -> int | None:
        v = _str(name)
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def _bool(name: str, default: bool = False) -> bool:
        v = _str(name)
        if v is None:
            return default
        return v.lower() in ("1", "true", "yes", "on")

    # Accept both our JS params and the server-render form fallback
    untapped_str = _str("untapped")
    if untapped_str is None:
        untapped_str = _str("untapped_other_init", "0") or "0"

    stop_at_100 = _bool("stop_at_100", False)
    if not stop_at_100:
        stop_at_100 = _bool("stop_when_counters_ge_100", False)

    req = SimRequest(
        untapped_other_init=int(untapped_str or "0"),
        stop_when_counters_ge_100=stop_at_100,
        stop_treasures_ge=_int("stop_treasures_ge"),
        stop_robots_ge=_int("stop_robots_ge"),
        stop_mana_ge=_int("stop_mana_ge"),
        has_delney=_bool("delney", False),
        seed=_int("seed"),
    )

    # Safety: if Delney is enabled and no stop condition is set, default to stop-at-100.
    # (Still also protected by engine caps.)
    if req.has_delney:
        has_any_stop = (
            req.stop_when_counters_ge_100
            or req.stop_treasures_ge is not None
            or req.stop_robots_ge is not None
            or req.stop_mana_ge is not None
        )
        if not has_any_stop:
            req.stop_when_counters_ge_100 = True

    return req


def _serialize_result(res) -> dict[str, Any]:
    fb = res.final_board_state
    return {
        "iterations": res.iterations,
        "roll_histogram": res.roll_histogram,
        "robots": fb.robots,
        "treasures": fb.treasures,
        "other": fb.other_artifacts,
        "puzzlebox": {
            "counters": fb.puzzlebox["counters"],
            "ready": fb.puzzlebox["ready_for_next_activation"],
            "mana": fb.mana,
        },
        "log": [
            {
                "iter": e.iter,
                "roll": e.roll,
                "created": e.created,
                "tapped_for_clock": e.tapped_for_clock,
                "note": e.note,
            }
            for e in res.roll_log
        ],
    }


@router.get("/api/simulate")
async def house_api_simulate(request: Request):
    try:
        req = _build_req_from_params(dict(request.query_params))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    res = simulate(req)
    return JSONResponse(_serialize_result(res))


@router.post("/run", name="run_sim", response_class=HTMLResponse)
async def house_run(request: Request) -> HTMLResponse:
    form = await request.form()
    req = _build_req_from_params(dict(form))
    res = simulate(req)
    result_json = json.dumps(_serialize_result(res))

    return templates.TemplateResponse(
        "house/index.html",
        {
            "request": request,
            "result_json": result_json,
            "seed": "" if req.seed is None else req.seed,
            "untapped_other_init": req.untapped_other_init,
            "stop_at_100": req.stop_when_counters_ge_100,
            "delney": req.has_delney,
            "stop_treasures_ge": "" if req.stop_treasures_ge is None else req.stop_treasures_ge,
            "stop_robots_ge": "" if req.stop_robots_ge is None else req.stop_robots_ge,
            "stop_mana_ge": "" if req.stop_mana_ge is None else req.stop_mana_ge,
        },
    )
