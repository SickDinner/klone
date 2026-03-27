from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .config import Settings, load_settings, settings
from .contracts import APP_VERSION
from .repository import KloneRepository


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = KloneRepository(resolved_settings.sqlite_path)
        bootstrap_report = repository.initialize()
        app.state.settings = resolved_settings
        app.state.repository = repository
        app.state.runtime_config = resolved_settings.runtime_snapshot()
        app.state.bootstrap_report = bootstrap_report
        yield

    app = FastAPI(
        title=resolved_settings.app_name,
        summary="Modular mission control server for a supervised personal clone system.",
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app(settings)
