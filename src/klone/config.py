from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("KLONE_APP_NAME", "Klone")
    environment: str = os.getenv("KLONE_ENV", "development")
    owner_debug_mode: bool = os.getenv("KLONE_OWNER_DEBUG", "true").lower() == "true"
    project_root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = Path(os.getenv("KLONE_DATA_DIR", str(project_root / "data")))
    sqlite_path: Path = Path(
        os.getenv("KLONE_DB_PATH", str(data_dir / "klone_mission_control.db"))
    )
    asset_preview_limit: int = int(os.getenv("KLONE_ASSET_PREVIEW_LIMIT", "40"))
    audit_preview_limit: int = int(os.getenv("KLONE_AUDIT_PREVIEW_LIMIT", "25"))


settings = Settings()
