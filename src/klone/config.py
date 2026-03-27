from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from .contracts import APP_VERSION, BOOTSTRAP_VERSION, MODULE_REGISTRY_VERSION, SCHEMA_VERSION


def _env_flag(environ: Mapping[str, str], key: str, default: bool) -> bool:
    raw_value = environ.get(key)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(environ: Mapping[str, str], key: str, default: int) -> int:
    raw_value = environ.get(key)
    if raw_value is None:
        return default
    return int(raw_value)


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    owner_debug_mode: bool
    project_root: Path
    data_dir: Path
    sqlite_path: Path
    asset_preview_limit: int
    audit_preview_limit: int

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        active_environ = environ or os.environ
        project_root = Path(__file__).resolve().parents[2]
        data_dir = Path(active_environ.get("KLONE_DATA_DIR", str(project_root / "data")))
        sqlite_path = Path(active_environ.get("KLONE_DB_PATH", str(data_dir / "klone_mission_control.db")))
        return cls(
            app_name=active_environ.get("KLONE_APP_NAME", "Klone"),
            environment=active_environ.get("KLONE_ENV", "development"),
            owner_debug_mode=_env_flag(active_environ, "KLONE_OWNER_DEBUG", default=True),
            project_root=project_root,
            data_dir=data_dir,
            sqlite_path=sqlite_path,
            asset_preview_limit=_env_int(active_environ, "KLONE_ASSET_PREVIEW_LIMIT", default=40),
            audit_preview_limit=_env_int(active_environ, "KLONE_AUDIT_PREVIEW_LIMIT", default=25),
        )

    def runtime_snapshot(self) -> dict[str, str | int | bool]:
        return {
            "app_name": self.app_name,
            "app_version": APP_VERSION,
            "environment": self.environment,
            "owner_debug_mode": self.owner_debug_mode,
            "project_root": str(self.project_root),
            "data_dir": str(self.data_dir),
            "database_path": str(self.sqlite_path),
            "asset_preview_limit": self.asset_preview_limit,
            "audit_preview_limit": self.audit_preview_limit,
            "bootstrap_version": BOOTSTRAP_VERSION,
            "schema_version": SCHEMA_VERSION,
            "module_registry_version": MODULE_REGISTRY_VERSION,
        }


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    return Settings.load(environ=environ)


settings = load_settings()
