from fastapi import APIRouter
from app.web.home import router as home_router
from app.features.treasure.routers import router as treasure_router
from app.features.house.routers import router as house_router

def make_root_router() -> APIRouter:
    root = APIRouter()
    root.include_router(home_router)
    root.include_router(treasure_router, prefix="/treasure", tags=["treasure"])
    root.include_router(house_router, prefix="/house", tags=["house"])
    return root
