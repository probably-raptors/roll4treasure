# roll4treasure-main/app/core/templates.py
from fastapi.templating import Jinja2Templates
from .config import settings

templates = Jinja2Templates(directory=settings.TEMPLATE_DIR)
