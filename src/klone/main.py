from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .config import Settings, load_settings, settings
from .contracts import APP_VERSION, BOOTSTRAP_TASK_ID
from .request_context import build_request_context
from .repository import KloneRepository, utc_now_iso
from .services import ServiceContainer
from .v1_api import router as v1_router


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        run_started_at = utc_now_iso()
        repository = KloneRepository(resolved_settings.sqlite_path)
        bootstrap_report = repository.initialize()
        bootstrap_ids = repository.build_internal_run_identifiers(
            run_kind="bootstrap",
            started_at=run_started_at,
            task_id=BOOTSTRAP_TASK_ID,
        )
        latest_internal_run = repository.record_internal_run(
            run_id=bootstrap_ids["run_id"],
            task_id=bootstrap_ids["task_id"],
            run_kind="bootstrap",
            status="completed",
            trigger="startup",
            trace_id=bootstrap_ids["trace_id"],
            started_at=run_started_at,
            completed_at=bootstrap_report["initialized_at"],
            metadata={
                "app_name": resolved_settings.app_name,
                "environment": resolved_settings.environment,
                "bootstrap_version": bootstrap_report["bootstrap_version"],
                "schema_version": bootstrap_report["schema_version"],
                "schema_user_version": bootstrap_report["schema_user_version"],
                "bootstrap_mode": bootstrap_report["bootstrap_mode"],
                "missing_tables": bootstrap_report["missing_tables"],
                "correction_schema_ready": bootstrap_report["correction_schema_ready"],
            },
        )
        app.state.settings = resolved_settings
        app.state.repository = repository
        app.state.runtime_config = resolved_settings.runtime_snapshot()
        app.state.bootstrap_report = bootstrap_report
        app.state.latest_internal_run = latest_internal_run
        app.state.services = ServiceContainer.build(repository)
        yield

    app = FastAPI(
        title=resolved_settings.app_name,
        summary="Modular mission control server for a supervised personal clone system.",
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    @app.middleware("http")
    async def request_context_middleware(request, call_next):
        request_context = build_request_context(request)
        request.state.request_context = request_context
        response = await call_next(request)
        for header_name, header_value in request_context.as_headers().items():
            response.headers[header_name] = header_value
        return response

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api_router)
    app.include_router(v1_router)

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app(settings)
