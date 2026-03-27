from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .config import settings
from .repository import KloneRepository


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = KloneRepository(settings.sqlite_path)
    repository.initialize()
    app.state.repository = repository
    yield


app = FastAPI(
    title=settings.app_name,
    summary="Modular mission control server for a supervised personal clone system.",
    version="0.2.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
