import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.web.routes_sim import router as sim_router
from app.web.routes_treasure import router as treasure_router
from app.treasure.store import init_pool, close_pool, periodic_cleanup

app = FastAPI(title="Roll 4 Treasure")

@app.on_event("startup")
async def _startup():
    # DB pool
    await init_pool()

    # TTL cleanup background task
    ttl_hours = int(os.getenv("SESSION_TTL_HOURS", "72"))              # default 72h
    interval_seconds = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "900"))  # default 15m
    app.state.cleanup_stop = asyncio.Event()
    app.state.cleanup_task = asyncio.create_task(
        periodic_cleanup(ttl_hours=ttl_hours, interval_seconds=interval_seconds, stop_event=app.state.cleanup_stop)
    )

@app.on_event("shutdown")
async def _shutdown():
    # stop cleanup loop
    stop = getattr(app.state, "cleanup_stop", None)
    task = getattr(app.state, "cleanup_task", None)
    if stop is not None:
        stop.set()
    if task is not None:
        try:
            await task
        except Exception:
            pass

    await close_pool()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

app.include_router(sim_router, prefix="/gamble")
app.include_router(treasure_router)
