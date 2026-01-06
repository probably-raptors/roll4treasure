from fastapi import APIRouter

from app.features.house.routers import router as house_router
from app.web.health import router as health_router
from app.web.home import router as home_router


def make_root_router() -> APIRouter:
    root = APIRouter()
    root.include_router(home_router)
    root.include_router(health_router)
    root.include_router(house_router, prefix="/house", tags=["house"])
    return root
