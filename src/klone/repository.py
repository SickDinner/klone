from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .contracts import ClassificationLevel, IngestStatus


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "dataset"


class KloneRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    # Schema bootstrap
    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    room_id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    description TEXT,
                    classification_level TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_scan_at TEXT,
                    scan_state TEXT
                );

                CREATE TABLE IF NOT EXISTS ingest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                    room_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger_source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    files_discovered INTEGER NOT NULL DEFAULT 0,
                    assets_indexed INTEGER NOT NULL DEFAULT 0,
                    new_assets INTEGER NOT NULL DEFAULT 0,
                    updated_assets INTEGER NOT NULL DEFAULT 0,
                    unchanged_assets INTEGER NOT NULL DEFAULT 0,
                    duplicates_detected INTEGER NOT NULL DEFAULT 0,
                    errors_detected INTEGER NOT NULL DEFAULT 0,
                    summary TEXT
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                    ingest_run_id INTEGER REFERENCES ingest_runs(id),
                    room_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    mime_type TEXT,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    asset_kind TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    extraction_status TEXT NOT NULL,
                    fs_created_at TEXT NOT NULL,
                    fs_modified_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    dedup_status TEXT NOT NULL DEFAULT 'unique',
                    canonical_asset_id INTEGER REFERENCES assets(id),
                    collection TEXT NOT NULL,
                    metadata_json TEXT,
                    UNIQUE(dataset_id, path)
                );

                CREATE INDEX IF NOT EXISTS idx_assets_dataset_id ON assets(dataset_id);
                CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);
                CREATE INDEX IF NOT EXISTS idx_runs_dataset_id ON ingest_runs(dataset_id);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    room_id TEXT,
                    classification_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
                    ON audit_events(created_at DESC);
                """
            )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _borrowed_connection(
        self, conn: sqlite3.Connection | None = None
    ) -> Iterator[sqlite3.Connection]:
        if conn is not None:
            yield conn
            return
        with self.connection() as managed:
            yield managed

    def _ensure_unique_slug(
        self, conn: sqlite3.Connection, base_slug: str, dataset_id: int | None = None
    ) -> str:
        slug = base_slug
        suffix = 2
        while True:
            if dataset_id is None:
                row = conn.execute("SELECT id FROM datasets WHERE slug = ?", (slug,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM datasets WHERE slug = ? AND id != ?",
                    (slug, dataset_id),
                ).fetchone()
            if row is None:
                return slug
            slug = f"{base_slug}-{suffix}"
            suffix += 1

    # Dataset persistence
    def upsert_dataset(
        self,
        *,
        label: str,
        root_path: str,
        room_id: str,
        collection: str,
        classification_level: ClassificationLevel,
        description: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                "SELECT * FROM datasets WHERE root_path = ?",
                (root_path,),
            ).fetchone()
            timestamp = utc_now_iso()
            if existing is not None:
                slug = self._ensure_unique_slug(active_conn, slugify(label), existing["id"])
                active_conn.execute(
                    """
                    UPDATE datasets
                    SET slug = ?,
                        label = ?,
                        room_id = ?,
                        collection = ?,
                        description = ?,
                        classification_level = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        slug,
                        label,
                        room_id,
                        collection,
                        description,
                        classification_level,
                        timestamp,
                        existing["id"],
                    ),
                )
                row = active_conn.execute(
                    "SELECT * FROM datasets WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                return dict(row), False

            slug = self._ensure_unique_slug(active_conn, slugify(label))
            cursor = active_conn.execute(
                """
                INSERT INTO datasets (
                    slug, label, root_path, room_id, collection, description,
                    classification_level, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    label,
                    root_path,
                    room_id,
                    collection,
                    description,
                    classification_level,
                    timestamp,
                    timestamp,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM datasets WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True

    def mark_dataset_scan_state(
        self,
        dataset_id: int,
        *,
        scan_state: IngestStatus,
        last_scan_at: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        with self._borrowed_connection(conn) as active_conn:
            active_conn.execute(
                """
                UPDATE datasets
                SET scan_state = ?, last_scan_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (scan_state, last_scan_at, utc_now_iso(), dataset_id),
            )

    # Ingest run persistence
    def start_ingest_run(
        self,
        dataset_id: int,
        *,
        room_id: str,
        trigger_source: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            started_at = utc_now_iso()
            cursor = active_conn.execute(
                """
                INSERT INTO ingest_runs (dataset_id, room_id, status, trigger_source, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (dataset_id, room_id, "running", trigger_source, started_at),
            )
            row = active_conn.execute(
                """
                SELECT ir.*, d.label AS dataset_label
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                WHERE ir.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)

    def finish_ingest_run(
        self,
        run_id: int,
        *,
        status: IngestStatus,
        files_discovered: int,
        assets_indexed: int,
        new_assets: int,
        updated_assets: int,
        unchanged_assets: int,
        duplicates_detected: int,
        errors_detected: int,
        summary: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            completed_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE ingest_runs
                SET status = ?,
                    completed_at = ?,
                    files_discovered = ?,
                    assets_indexed = ?,
                    new_assets = ?,
                    updated_assets = ?,
                    unchanged_assets = ?,
                    duplicates_detected = ?,
                    errors_detected = ?,
                    summary = ?
                WHERE id = ?
                """,
                (
                    status,
                    completed_at,
                    files_discovered,
                    assets_indexed,
                    new_assets,
                    updated_assets,
                    unchanged_assets,
                    duplicates_detected,
                    errors_detected,
                    summary,
                    run_id,
                ),
            )
            row = active_conn.execute(
                """
                SELECT ir.*, d.label AS dataset_label
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                WHERE ir.id = ?
                """,
                (run_id,),
            ).fetchone()
            return dict(row)

    # Audit persistence
    def record_audit_event(
        self,
        *,
        event_type: str,
        actor: str,
        target_type: str,
        target_id: str | None,
        room_id: str | None,
        classification_level: ClassificationLevel,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            created_at = utc_now_iso()
            metadata_json = json.dumps(metadata, sort_keys=True) if metadata else None
            cursor = active_conn.execute(
                """
                INSERT INTO audit_events (
                    event_type, actor, target_type, target_id, room_id, classification_level,
                    summary, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    actor,
                    target_type,
                    target_id,
                    room_id,
                    classification_level,
                    summary,
                    metadata_json,
                    created_at,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM audit_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)

    # Asset persistence
    def upsert_asset(
        self,
        dataset_id: int,
        ingest_run_id: int,
        asset: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM assets
                WHERE dataset_id = ? AND path = ?
                """,
                (dataset_id, asset["path"]),
            ).fetchone()
            canonical = active_conn.execute(
                """
                SELECT id
                FROM assets
                WHERE sha256 = ?
                  AND NOT (dataset_id = ? AND path = ?)
                ORDER BY id
                LIMIT 1
                """,
                (asset["sha256"], dataset_id, asset["path"]),
            ).fetchone()
            dedup_status = "duplicate" if canonical is not None else "unique"
            canonical_asset_id = canonical["id"] if canonical is not None else None
            metadata_json = json.dumps(asset["metadata"], sort_keys=True)

            if existing is not None:
                action = "updated" if existing["sha256"] != asset["sha256"] else "unchanged"
                active_conn.execute(
                    """
                    UPDATE assets
                    SET ingest_run_id = ?,
                        room_id = ?,
                        relative_path = ?,
                        file_name = ?,
                        extension = ?,
                        mime_type = ?,
                        size_bytes = ?,
                        sha256 = ?,
                        asset_kind = ?,
                        classification_level = ?,
                        extraction_status = ?,
                        fs_created_at = ?,
                        fs_modified_at = ?,
                        indexed_at = ?,
                        last_seen_at = ?,
                        dedup_status = ?,
                        canonical_asset_id = ?,
                        collection = ?,
                        metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        ingest_run_id,
                        asset["room_id"],
                        asset["relative_path"],
                        asset["file_name"],
                        asset["extension"],
                        asset["mime_type"],
                        asset["size_bytes"],
                        asset["sha256"],
                        asset["asset_kind"],
                        asset["classification_level"],
                        asset["extraction_status"],
                        asset["fs_created_at"],
                        asset["fs_modified_at"],
                        asset["indexed_at"],
                        asset["indexed_at"],
                        dedup_status,
                        canonical_asset_id,
                        asset["collection"],
                        metadata_json,
                        existing["id"],
                    ),
                )
                asset_id = existing["id"]
            else:
                cursor = active_conn.execute(
                    """
                    INSERT INTO assets (
                        dataset_id, ingest_run_id, room_id, path, relative_path, file_name,
                        extension, mime_type, size_bytes, sha256, asset_kind,
                        classification_level, extraction_status, fs_created_at, fs_modified_at,
                        indexed_at, first_seen_at, last_seen_at, dedup_status, canonical_asset_id,
                        collection, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_id,
                        ingest_run_id,
                        asset["room_id"],
                        asset["path"],
                        asset["relative_path"],
                        asset["file_name"],
                        asset["extension"],
                        asset["mime_type"],
                        asset["size_bytes"],
                        asset["sha256"],
                        asset["asset_kind"],
                        asset["classification_level"],
                        asset["extraction_status"],
                        asset["fs_created_at"],
                        asset["fs_modified_at"],
                        asset["indexed_at"],
                        asset["indexed_at"],
                        asset["indexed_at"],
                        dedup_status,
                        canonical_asset_id,
                        asset["collection"],
                        metadata_json,
                    ),
                )
                asset_id = cursor.lastrowid
                action = "new"

            row = active_conn.execute(
                """
                SELECT a.*, d.label AS dataset_label
                FROM assets a
                JOIN datasets d ON d.id = a.dataset_id
                WHERE a.id = ?
                """,
                (asset_id,),
            ).fetchone()
            return {
                "record": dict(row),
                "action": action,
                "is_duplicate": dedup_status == "duplicate",
            }

    def list_datasets(self, *, room_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT d.*,
                       COUNT(a.id) AS asset_count,
                       COALESCE(SUM(CASE WHEN a.dedup_status = 'duplicate' THEN 1 ELSE 0 END), 0)
                         AS duplicate_count
                FROM datasets d
                LEFT JOIN assets a ON a.dataset_id = d.id
                WHERE d.room_id = ?
                GROUP BY d.id
                ORDER BY d.updated_at DESC
                """,
                (room_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_assets(
        self,
        *,
        room_id: str,
        dataset_id: int | None = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            query = """
                SELECT a.*, d.label AS dataset_label
                FROM assets a
                JOIN datasets d ON d.id = a.dataset_id
                WHERE a.room_id = ?
            """
            params: list[Any] = [room_id]
            if dataset_id is not None:
                query += " AND a.dataset_id = ?"
                params.append(dataset_id)
            query += " ORDER BY a.indexed_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_asset(self, asset_id: int, *, room_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT a.*, d.label AS dataset_label
                FROM assets a
                JOIN datasets d ON d.id = a.dataset_id
                WHERE a.id = ? AND a.room_id = ?
                """,
                (asset_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_ingest_runs(self, *, room_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT ir.*, d.label AS dataset_label
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                WHERE ir.room_id = ?
                ORDER BY ir.started_at DESC
                LIMIT ?
                """,
                (room_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def latest_ingest_run(
        self,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT ir.*, d.label AS dataset_label
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                WHERE ir.room_id = ?
                ORDER BY ir.started_at DESC
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    # Audit queries
    def list_audit_events(self, *, room_id: str, limit: int = 25) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_events
                WHERE room_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (room_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def counts_for_room(
        self,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, int]:
        with self._borrowed_connection(conn) as active_conn:
            dataset_count = active_conn.execute(
                "SELECT COUNT(*) FROM datasets WHERE room_id = ?",
                (room_id,),
            ).fetchone()[0]
            asset_count = active_conn.execute(
                "SELECT COUNT(*) FROM assets WHERE room_id = ?",
                (room_id,),
            ).fetchone()[0]
            duplicate_count = active_conn.execute(
                "SELECT COUNT(*) FROM assets WHERE room_id = ? AND dedup_status = 'duplicate'",
                (room_id,),
            ).fetchone()[0]
            audit_count = active_conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE room_id = ?",
                (room_id,),
            ).fetchone()[0]
            return {
                "dataset_count": int(dataset_count),
                "asset_count": int(asset_count),
                "duplicate_count": int(duplicate_count),
                "audit_event_count": int(audit_count),
            }
