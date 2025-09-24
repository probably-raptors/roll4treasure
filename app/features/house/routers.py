from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.templates import templates
from app.features.house.models import SimRequest
from app.features.house.engine import simulate

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def house_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("house/index.html", {"request": request})


def _build_req_from_params(params: Dict[str, Any]) -> SimRequest:
    def _str(name: str, default: Optional[str] = None) -> Optional[str]:
        v = params.get(name, default)
        return None if v in ("", None) else str(v)

    def _int(name: str) -> Optional[int]:
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

    # Accepts both our JS params and the server-render form fallback
    return SimRequest(
        untapped_other_init=int(_str("untapped", "0") or "0"),
        stop_when_counters_ge_100=_bool("stop_at_100", False),
        stop_treasures_ge=_int("stop_treasures_ge"),
        stop_robots_ge=_int("stop_robots_ge"),
        stop_mana_ge=_int("stop_mana_ge"),
        seed=_int("seed"),
    )


def _serialize_result(res) -> Dict[str, Any]:
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
    req = _build_req_from_params(dict(request.query_params))
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
            "seed": req.seed,
            "untapped_other_init": req.untapped_other_init,
            "stop_at_100": req.stop_when_counters_ge_100,
        },
    )
