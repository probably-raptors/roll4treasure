from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.sim.models import SimRequest
from app.sim.engine import simulate
from .ui import render_index

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    ctx = render_index({"untapped_other_init": 0})
    return templates.TemplateResponse("house.html", {"request": request, **ctx})

@router.post("/", name="run_sim", response_class=HTMLResponse)
async def run_sim(
    request: Request,
    untapped_other_init: int = Form(...),
    stop_when_counters_ge_100: bool = Form(False),
    stop_treasures_ge: str = Form(""),
    stop_robots_ge: str = Form(""),
    stop_mana_ge: str = Form(""),
    seed: str = Form(""),
    max_iters: int = Form(10_000_000),
):
    # Let Pydantic coerce blanks to None per the validator we added
    req = SimRequest(
        untapped_other_init=untapped_other_init,
        stop_when_counters_ge_100=stop_when_counters_ge_100,
        stop_treasures_ge=stop_treasures_ge,
        stop_robots_ge=stop_robots_ge,
        stop_mana_ge=stop_mana_ge,
        seed=seed,
        max_iters=max_iters,
    )
    result = simulate(req).model_dump()
    ctx = render_index(req.model_dump(), result)
    return templates.TemplateResponse("house.html", {"request": request, **ctx})

@router.get("/simulate")
async def api_simulate(
    untapped: int = Query(..., ge=0),
    stop_at_100: bool = Query(False),
    seed: int | None = Query(None),
    max_iters: int = Query(10_000_000, ge=1),
):
    req = SimRequest(
        untapped_other_init=untapped,
        stop_when_counters_ge_100=stop_at_100,
        seed=seed,
        max_iters=max_iters,
    )
    return JSONResponse(simulate(req).model_dump())
