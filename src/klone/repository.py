from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .contracts import (
    BOOTSTRAP_VERSION,
    BOOTSTRAP_TASK_ID,
    ClassificationLevel,
    INTERNAL_RUN_KIND_VALUES,
    INTERNAL_RUN_STATUS_VALUES,
    INTERNAL_RUN_TRIGGER_VALUES,
    INGEST_QUEUE_STATUS_VALUES,
    IngestStatus,
    IngestQueueStatus,
    MEMORY_STATUS_VALUES,
    MemoryStatus,
    SCHEMA_USER_VERSION,
    SCHEMA_VERSION,
    SYSTEM_SCOPE_ID,
)


EXPECTED_TABLES = (
    "assets",
    "audit_events",
    "control_plane_audit_chain",
    "datasets",
    "ingest_queue_jobs",
    "ingest_run_manifests",
    "ingest_runs",
    "internal_runs",
    "memory_entities",
    "memory_episode_events",
    "memory_episodes",
    "memory_event_entities",
    "memory_event_supersessions",
    "memory_events",
    "memory_provenance",
    "world_memory_depth_jobs",
    "world_memory_depth_results",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "dataset"


class KloneRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._bootstrap_report: dict[str, Any] | None = None

    # Schema bootstrap
    def initialize(self) -> dict[str, Any]:
        database_preexisting = self.db_path.exists()
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

                CREATE TABLE IF NOT EXISTS ingest_queue_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    normalized_root_path TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    description TEXT,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_run_id INTEGER REFERENCES ingest_runs(id),
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS ingest_run_manifests (
                    ingest_run_id INTEGER PRIMARY KEY REFERENCES ingest_runs(id),
                    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
                    room_id TEXT NOT NULL,
                    normalized_root_path TEXT NOT NULL,
                    total_size_bytes INTEGER NOT NULL DEFAULT 0,
                    sample_limit INTEGER NOT NULL DEFAULT 12,
                    asset_kind_breakdown_json TEXT,
                    sample_assets_json TEXT,
                    warnings_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS world_memory_depth_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    renderer TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_node_ids_json TEXT NOT NULL,
                    result_count INTEGER NOT NULL DEFAULT 0,
                    notes_json TEXT,
                    warnings_json TEXT,
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS world_memory_depth_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES world_memory_depth_jobs(id) ON DELETE CASCADE,
                    room_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    cluster_id TEXT NOT NULL,
                    asset_id INTEGER NOT NULL REFERENCES assets(id),
                    label TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    asset_kind TEXT NOT NULL,
                    renderer TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_image_path TEXT NOT NULL,
                    depth_preview_path TEXT NOT NULL,
                    depth_raw_path TEXT NOT NULL,
                    width_px INTEGER NOT NULL,
                    height_px INTEGER NOT NULL,
                    notes_json TEXT,
                    warnings_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
                CREATE INDEX IF NOT EXISTS idx_ingest_queue_jobs_room_created_at
                    ON ingest_queue_jobs(room_id, created_at DESC, id DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_queue_jobs_active_root
                    ON ingest_queue_jobs(room_id, normalized_root_path)
                    WHERE status IN ('queued', 'running');
                CREATE INDEX IF NOT EXISTS idx_ingest_run_manifests_room_created_at
                    ON ingest_run_manifests(room_id, created_at DESC, ingest_run_id DESC);
                CREATE INDEX IF NOT EXISTS idx_world_memory_depth_jobs_room_created_at
                    ON world_memory_depth_jobs(room_id, created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_world_memory_depth_results_job_id
                    ON world_memory_depth_results(job_id, id ASC);
                CREATE INDEX IF NOT EXISTS idx_world_memory_depth_results_room_node
                    ON world_memory_depth_results(room_id, node_id, updated_at DESC, id DESC);

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

                CREATE TABLE IF NOT EXISTS control_plane_audit_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    route_path TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    principal TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT,
                    prev_event_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_control_plane_audit_chain_created_at
                    ON control_plane_audit_chain(created_at DESC, id DESC);

                CREATE TABLE IF NOT EXISTS internal_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    room_id TEXT,
                    trace_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_internal_runs_started_at
                    ON internal_runs(started_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_internal_runs_task_id
                    ON internal_runs(task_id, started_at DESC);

                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    dataset_id INTEGER REFERENCES datasets(id),
                    asset_id INTEGER REFERENCES assets(id),
                    ingest_run_id INTEGER REFERENCES ingest_runs(id),
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    evidence_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','rejected','superseded')),
                    correction_reason TEXT,
                    superseded_by_id INTEGER,
                    corrected_at TEXT,
                    corrected_by_role TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room_id, source_table, source_record_id, event_type)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_events_room_occurred_at
                    ON memory_events(room_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_events_room_ingest_run
                    ON memory_events(room_id, ingest_run_id);

                CREATE TABLE IF NOT EXISTS memory_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    canonical_key TEXT NOT NULL,
                    seed_source_event_id INTEGER NOT NULL REFERENCES memory_events(id),
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room_id, entity_type, canonical_key)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_entities_room_canonical_name
                    ON memory_entities(room_id, canonical_name ASC);
                CREATE INDEX IF NOT EXISTS idx_memory_entities_room_last_seen
                    ON memory_entities(room_id, last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS memory_episodes (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    episode_type TEXT NOT NULL,
                    grouping_basis TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','rejected','superseded')),
                    correction_reason TEXT,
                    corrected_at TEXT,
                    corrected_by_role TEXT,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room_id, source_table, source_record_id, episode_type)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_episodes_room_start
                    ON memory_episodes(room_id, start_at DESC);

                CREATE TABLE IF NOT EXISTS memory_event_entities (
                    event_id INTEGER NOT NULL REFERENCES memory_events(id),
                    entity_id INTEGER NOT NULL REFERENCES memory_entities(id),
                    role TEXT NOT NULL,
                    source_basis TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_id, entity_id, role)
                );

                CREATE TABLE IF NOT EXISTS memory_episode_events (
                    episode_id TEXT NOT NULL REFERENCES memory_episodes(id),
                    event_id INTEGER NOT NULL REFERENCES memory_events(id),
                    sequence_no INTEGER NOT NULL,
                    inclusion_basis TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(episode_id, event_id)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_episode_events_episode_sequence
                    ON memory_episode_events(episode_id, sequence_no ASC);

                CREATE TABLE IF NOT EXISTS memory_event_supersessions (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    old_event_id TEXT NOT NULL,
                    new_event_id TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    created_by_role TEXT NOT NULL,
                    UNIQUE(room_id, old_event_id, new_event_id)
                );

                CREATE TABLE IF NOT EXISTS memory_provenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    provenance_type TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    source_field TEXT,
                    basis_type TEXT NOT NULL,
                    basis_value TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memory_provenance_owner
                    ON memory_provenance(room_id, owner_type, owner_id);
                CREATE INDEX IF NOT EXISTS idx_memory_provenance_source
                    ON memory_provenance(room_id, source_table, source_record_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_provenance_unique
                    ON memory_provenance(
                        room_id,
                        owner_type,
                        owner_id,
                        provenance_type,
                        source_table,
                        source_record_id,
                        ifnull(source_field, ''),
                        basis_type,
                        ifnull(basis_value, '')
                    );
                """
            )
            self._ensure_column(
                conn,
                table_name="memory_events",
                column_name="status",
                column_sql="status TEXT NOT NULL DEFAULT 'active'",
            )
            self._ensure_column(
                conn,
                table_name="memory_events",
                column_name="correction_reason",
                column_sql="correction_reason TEXT",
            )
            self._ensure_column(
                conn,
                table_name="memory_events",
                column_name="superseded_by_id",
                column_sql="superseded_by_id INTEGER",
            )
            self._ensure_column(
                conn,
                table_name="memory_events",
                column_name="corrected_at",
                column_sql="corrected_at TEXT",
            )
            self._ensure_column(
                conn,
                table_name="memory_events",
                column_name="corrected_by_role",
                column_sql="corrected_by_role TEXT",
            )
            self._ensure_column(
                conn,
                table_name="memory_episodes",
                column_name="status",
                column_sql="status TEXT NOT NULL DEFAULT 'active'",
            )
            self._ensure_column(
                conn,
                table_name="memory_episodes",
                column_name="correction_reason",
                column_sql="correction_reason TEXT",
            )
            self._ensure_column(
                conn,
                table_name="memory_episodes",
                column_name="corrected_at",
                column_sql="corrected_at TEXT",
            )
            self._ensure_column(
                conn,
                table_name="memory_episodes",
                column_name="corrected_by_role",
                column_sql="corrected_by_role TEXT",
            )
            conn.execute("UPDATE memory_events SET status = 'active' WHERE status IS NULL")
            conn.execute("UPDATE memory_episodes SET status = 'active' WHERE status IS NULL")
            conn.execute(f"PRAGMA user_version = {SCHEMA_USER_VERSION}")
            self._bootstrap_report = self._build_bootstrap_report(
                conn,
                database_preexisting=database_preexisting,
            )
            return dict(self._bootstrap_report)

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

    def _encode_metadata(self, metadata: Mapping[str, Any] | None) -> str | None:
        return json.dumps(metadata, sort_keys=True) if metadata else None

    def _compute_control_plane_event_hash(
        self,
        *,
        event_type: str,
        route_path: str,
        actor: str,
        actor_role: str,
        principal: str,
        request_id: str,
        trace_id: str,
        status_code: int,
        summary: str,
        metadata_json: str | None,
        prev_event_hash: str | None,
        created_at: str,
    ) -> str:
        payload = {
            "event_type": event_type,
            "route_path": route_path,
            "actor": actor,
            "actor_role": actor_role,
            "principal": principal,
            "request_id": request_id,
            "trace_id": trace_id,
            "status_code": status_code,
            "summary": summary,
            "metadata_json": metadata_json,
            "prev_event_hash": prev_event_hash,
            "created_at": created_at,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return __import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_memory_status(
        self,
        *,
        status: MemoryStatus,
        superseded_by_id: int | None = None,
    ) -> None:
        if status not in MEMORY_STATUS_VALUES:
            raise ValueError(f"Unsupported memory status: {status}")
        if status == "superseded" and superseded_by_id is None:
            raise ValueError("Superseded memory events require superseded_by_id.")
        if status != "superseded" and superseded_by_id is not None:
            raise ValueError("superseded_by_id is only valid for superseded memory events.")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        column_sql: str,
    ) -> None:
        existing_columns = {
            row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    def _validate_internal_run(
        self,
        *,
        run_kind: str,
        status: str,
        trigger: str,
    ) -> None:
        if run_kind not in INTERNAL_RUN_KIND_VALUES:
            raise ValueError(f"Unsupported internal run kind: {run_kind}")
        if status not in INTERNAL_RUN_STATUS_VALUES:
            raise ValueError(f"Unsupported internal run status: {status}")
        if trigger not in INTERNAL_RUN_TRIGGER_VALUES:
            raise ValueError(f"Unsupported internal run trigger: {trigger}")

    def _list_tables(self, conn: sqlite3.Connection) -> list[str]:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name ASC
            """
        ).fetchall()
        return [str(row["name"]) for row in rows]

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _build_bootstrap_report(
        self,
        conn: sqlite3.Connection,
        *,
        database_preexisting: bool,
    ) -> dict[str, Any]:
        actual_tables = self._list_tables(conn)
        actual_table_set = set(actual_tables)
        missing_tables = sorted(table for table in EXPECTED_TABLES if table not in actual_table_set)
        memory_event_columns = self._table_columns(conn, "memory_events")
        memory_episode_columns = self._table_columns(conn, "memory_episodes")
        correction_schema_ready = (
            "memory_event_supersessions" in actual_table_set
            and {"status", "correction_reason", "corrected_at", "corrected_by_role"}.issubset(
                memory_episode_columns
            )
            and {
                "status",
                "correction_reason",
                "superseded_by_id",
                "corrected_at",
                "corrected_by_role",
            }.issubset(memory_event_columns)
        )
        schema_user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        return {
            "bootstrap_version": BOOTSTRAP_VERSION,
            "schema_version": SCHEMA_VERSION,
            "schema_user_version": schema_user_version,
            "bootstrap_mode": "existing_db" if database_preexisting else "fresh_db",
            "database_path": str(self.db_path),
            "initialized_at": utc_now_iso(),
            "expected_tables": list(EXPECTED_TABLES),
            "actual_tables": actual_tables,
            "missing_tables": missing_tables,
            "correction_schema_ready": correction_schema_ready,
        }

    def bootstrap_report(self) -> dict[str, Any]:
        if self._bootstrap_report is not None:
            return dict(self._bootstrap_report)
        with self.connection() as conn:
            self._bootstrap_report = self._build_bootstrap_report(
                conn,
                database_preexisting=self.db_path.exists(),
            )
            return dict(self._bootstrap_report)

    def build_internal_run_identifiers(
        self,
        *,
        run_kind: str,
        started_at: str,
        room_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, str]:
        scope = room_id or SYSTEM_SCOPE_ID
        effective_task_id = task_id or BOOTSTRAP_TASK_ID
        run_id = f"run:{run_kind}:{scope}:{started_at}"
        trace_id = f"trace:{run_kind}:{scope}:{started_at}"
        return {
            "task_id": effective_task_id,
            "run_id": run_id,
            "trace_id": trace_id,
        }

    def record_internal_run(
        self,
        *,
        run_id: str,
        task_id: str,
        run_kind: str,
        status: str,
        trigger: str,
        trace_id: str,
        started_at: str,
        completed_at: str | None = None,
        room_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self._validate_internal_run(run_kind=run_kind, status=status, trigger=trigger)
        with self._borrowed_connection(conn) as active_conn:
            active_conn.execute(
                """
                INSERT INTO internal_runs (
                    id,
                    task_id,
                    run_kind,
                    status,
                    trigger,
                    room_id,
                    trace_id,
                    started_at,
                    completed_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    run_kind = excluded.run_kind,
                    status = excluded.status,
                    trigger = excluded.trigger,
                    room_id = excluded.room_id,
                    trace_id = excluded.trace_id,
                    started_at = excluded.started_at,
                    completed_at = COALESCE(excluded.completed_at, internal_runs.completed_at),
                    metadata_json = COALESCE(excluded.metadata_json, internal_runs.metadata_json)
                """,
                (
                    run_id,
                    task_id,
                    run_kind,
                    status,
                    trigger,
                    room_id,
                    trace_id,
                    started_at,
                    completed_at,
                    self._encode_metadata(metadata),
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM internal_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            return dict(row)

    def list_internal_runs(self, *, limit: int = 10) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM internal_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def latest_internal_run(self) -> dict[str, Any] | None:
        rows = self.list_internal_runs(limit=1)
        return rows[0] if rows else None

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

    def get_dataset_by_root_path(
        self,
        root_path: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT d.*,
                       COUNT(a.id) AS asset_count,
                       COALESCE(SUM(CASE WHEN a.dedup_status = 'duplicate' THEN 1 ELSE 0 END), 0)
                         AS duplicate_count
                FROM datasets d
                LEFT JOIN assets a ON a.dataset_id = d.id
                WHERE d.root_path = ?
                GROUP BY d.id
                """,
                (root_path,),
            ).fetchone()
            return dict(row) if row is not None else None

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

    # Ingest queue persistence
    def enqueue_ingest_queue_job(
        self,
        *,
        label: str,
        normalized_root_path: str,
        room_id: str,
        classification_level: ClassificationLevel,
        collection: str,
        description: str | None,
        request_payload: Mapping[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE room_id = ? AND normalized_root_path = ? AND status IN ('queued', 'running', 'interrupted')
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (room_id, normalized_root_path),
            ).fetchone()
            if existing is not None:
                return dict(existing), False

            created_at = utc_now_iso()
            cursor = active_conn.execute(
                """
                INSERT INTO ingest_queue_jobs (
                    label,
                    normalized_root_path,
                    room_id,
                    classification_level,
                    collection,
                    description,
                    request_json,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    label,
                    normalized_root_path,
                    room_id,
                    classification_level,
                    collection,
                    description,
                    json.dumps(request_payload, sort_keys=True),
                    "queued",
                    created_at,
                    created_at,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True

    def list_ingest_queue_jobs(
        self,
        *,
        room_id: str,
        limit: int = 16,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE room_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (room_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_ingest_queue_jobs(
        self,
        *,
        room_id: str,
        statuses: tuple[IngestQueueStatus, ...] = ("queued",),
        conn: sqlite3.Connection | None = None,
    ) -> int:
        if not statuses:
            return 0
        for status in statuses:
            if status not in INGEST_QUEUE_STATUS_VALUES:
                raise ValueError(f"Unsupported ingest queue status: {status}")
        placeholders = ", ".join("?" for _ in statuses)
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                f"""
                SELECT COUNT(*)
                FROM ingest_queue_jobs
                WHERE room_id = ?
                  AND status IN ({placeholders})
                """,
                (room_id, *statuses),
            ).fetchone()
            return int(row[0]) if row is not None else 0

    def get_ingest_queue_job(
        self,
        job_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE id = ? AND room_id = ?
                """,
                (job_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def start_ingest_queue_job(
        self,
        job_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            current = self.get_ingest_queue_job(job_id, room_id=room_id, conn=active_conn)
            if current is None:
                raise ValueError(f"Ingest queue job {job_id} was not found in room {room_id}.")
            if current["status"] not in {"queued", "failed", "interrupted"}:
                raise ValueError(
                    f"Ingest queue job {job_id} cannot start from status {current['status']}."
                )
            started_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE ingest_queue_jobs
                SET status = ?,
                    started_at = ?,
                    completed_at = NULL,
                    updated_at = ?,
                    attempt_count = attempt_count + 1,
                    last_error = NULL
                WHERE id = ? AND room_id = ?
                """,
                ("running", started_at, started_at, job_id, room_id),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE id = ? AND room_id = ?
                """,
                (job_id, room_id),
            ).fetchone()
            return dict(row)

    def recover_interrupted_ingest_queue_jobs(
        self,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE status = 'running'
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
            if not rows:
                return []
            recovered_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE ingest_queue_jobs
                SET status = 'interrupted',
                    updated_at = ?,
                    last_error = CASE
                        WHEN last_error IS NULL OR last_error = '' THEN 'interrupted_before_completion'
                        ELSE last_error
                    END
                WHERE status = 'running'
                """,
                (recovered_at,),
            )
            recovered_rows = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE status = 'interrupted'
                  AND updated_at = ?
                ORDER BY id DESC
                """,
                (recovered_at,),
            ).fetchall()
            return [dict(row) for row in recovered_rows]

    def finish_ingest_queue_job(
        self,
        job_id: int,
        *,
        room_id: str,
        status: IngestQueueStatus,
        last_run_id: int | None = None,
        last_error: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError(f"Unsupported ingest queue terminal status: {status}")
        with self._borrowed_connection(conn) as active_conn:
            completed_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE ingest_queue_jobs
                SET status = ?,
                    completed_at = ?,
                    updated_at = ?,
                    last_run_id = ?,
                    last_error = ?
                WHERE id = ? AND room_id = ?
                """,
                (status, completed_at, completed_at, last_run_id, last_error, job_id, room_id),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM ingest_queue_jobs
                WHERE id = ? AND room_id = ?
                """,
                (job_id, room_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"Ingest queue job {job_id} was not found in room {room_id}.")
            return dict(row)

    def cancel_ingest_queue_job(
        self,
        job_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            current = self.get_ingest_queue_job(job_id, room_id=room_id, conn=active_conn)
            if current is None:
                raise ValueError(f"Ingest queue job {job_id} was not found in room {room_id}.")
            if current["status"] not in {"queued", "failed", "interrupted"}:
                raise ValueError(
                    f"Ingest queue job {job_id} cannot be cancelled from status {current['status']}."
                )
            return self.finish_ingest_queue_job(
                job_id,
                room_id=room_id,
                status="cancelled",
                last_run_id=current.get("last_run_id"),
                last_error=current.get("last_error"),
                conn=active_conn,
            )

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

    def record_control_plane_audit_event(
        self,
        *,
        event_type: str,
        route_path: str,
        actor: str,
        actor_role: str,
        principal: str,
        request_id: str,
        trace_id: str,
        status_code: int,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            created_at = utc_now_iso()
            metadata_json = self._encode_metadata(metadata)
            previous_row = active_conn.execute(
                """
                SELECT event_hash
                FROM control_plane_audit_chain
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            prev_event_hash = str(previous_row["event_hash"]) if previous_row is not None else None
            event_hash = self._compute_control_plane_event_hash(
                event_type=event_type,
                route_path=route_path,
                actor=actor,
                actor_role=actor_role,
                principal=principal,
                request_id=request_id,
                trace_id=trace_id,
                status_code=status_code,
                summary=summary,
                metadata_json=metadata_json,
                prev_event_hash=prev_event_hash,
                created_at=created_at,
            )
            cursor = active_conn.execute(
                """
                INSERT INTO control_plane_audit_chain (
                    event_type,
                    route_path,
                    actor,
                    actor_role,
                    principal,
                    request_id,
                    trace_id,
                    status_code,
                    summary,
                    metadata_json,
                    prev_event_hash,
                    event_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    route_path,
                    actor,
                    actor_role,
                    principal,
                    request_id,
                    trace_id,
                    status_code,
                    summary,
                    metadata_json,
                    prev_event_hash,
                    event_hash,
                    created_at,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM control_plane_audit_chain WHERE id = ?",
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
            existing = self.get_asset_by_dataset_path(
                dataset_id,
                path=str(asset["path"]),
                conn=active_conn,
            )
            canonical = self.find_duplicate_asset_candidate(
                sha256=str(asset["sha256"]),
                dataset_id=dataset_id,
                path=str(asset["path"]),
                conn=active_conn,
            )
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

    def get_asset_by_dataset_path(
        self,
        dataset_id: int,
        *,
        path: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT *
                FROM assets
                WHERE dataset_id = ? AND path = ?
                """,
                (dataset_id, path),
            ).fetchone()
            return dict(row) if row is not None else None

    def find_duplicate_asset_candidate(
        self,
        *,
        sha256: str,
        dataset_id: int | None = None,
        path: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            query = """
                SELECT a.id,
                       a.dataset_id,
                       a.path,
                       a.relative_path,
                       a.room_id,
                       a.dedup_status,
                       d.label AS dataset_label
                FROM assets a
                JOIN datasets d ON d.id = a.dataset_id
                WHERE a.sha256 = ?
            """
            params: list[Any] = [sha256]
            if dataset_id is not None and path is not None:
                query += " AND NOT (a.dataset_id = ? AND a.path = ?)"
                params.extend([dataset_id, path])
            query += " ORDER BY a.id ASC LIMIT 1"
            row = active_conn.execute(query, params).fetchone()
            return dict(row) if row is not None else None

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

    def get_dataset(
        self,
        dataset_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT d.*,
                       COUNT(a.id) AS asset_count,
                       COALESCE(SUM(CASE WHEN a.dedup_status = 'duplicate' THEN 1 ELSE 0 END), 0)
                         AS duplicate_count
                FROM datasets d
                LEFT JOIN assets a ON a.dataset_id = d.id
                WHERE d.id = ? AND d.room_id = ?
                GROUP BY d.id
                """,
                (dataset_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

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

    # World-memory depth job persistence
    def create_world_memory_depth_job(
        self,
        *,
        room_id: str,
        renderer: str,
        requested_node_ids: list[str],
        notes: list[str] | None = None,
        warnings: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            created_at = utc_now_iso()
            cursor = active_conn.execute(
                """
                INSERT INTO world_memory_depth_jobs (
                    room_id,
                    renderer,
                    status,
                    requested_node_ids_json,
                    result_count,
                    notes_json,
                    warnings_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    room_id,
                    renderer,
                    "queued",
                    json.dumps(requested_node_ids, sort_keys=True),
                    json.dumps(notes or [], sort_keys=True),
                    json.dumps(warnings or [], sort_keys=True),
                    created_at,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM world_memory_depth_jobs WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)

    def mark_world_memory_depth_job_running(
        self,
        *,
        job_id: int,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            started_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE world_memory_depth_jobs
                SET status = ?, started_at = ?, completed_at = NULL, error_text = NULL
                WHERE id = ? AND room_id = ?
                """,
                ("running", started_at, job_id, room_id),
            )
            row = active_conn.execute(
                "SELECT * FROM world_memory_depth_jobs WHERE id = ? AND room_id = ?",
                (job_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def complete_world_memory_depth_job(
        self,
        *,
        job_id: int,
        room_id: str,
        result_count: int,
        notes: list[str] | None = None,
        warnings: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            completed_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE world_memory_depth_jobs
                SET status = ?,
                    result_count = ?,
                    notes_json = ?,
                    warnings_json = ?,
                    completed_at = ?,
                    error_text = NULL
                WHERE id = ? AND room_id = ?
                """,
                (
                    "completed",
                    result_count,
                    json.dumps(notes or [], sort_keys=True),
                    json.dumps(warnings or [], sort_keys=True),
                    completed_at,
                    job_id,
                    room_id,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM world_memory_depth_jobs WHERE id = ? AND room_id = ?",
                (job_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def fail_world_memory_depth_job(
        self,
        *,
        job_id: int,
        room_id: str,
        error_text: str,
        notes: list[str] | None = None,
        warnings: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            completed_at = utc_now_iso()
            active_conn.execute(
                """
                UPDATE world_memory_depth_jobs
                SET status = ?,
                    notes_json = ?,
                    warnings_json = ?,
                    error_text = ?,
                    completed_at = ?
                WHERE id = ? AND room_id = ?
                """,
                (
                    "failed",
                    json.dumps(notes or [], sort_keys=True),
                    json.dumps(warnings or [], sort_keys=True),
                    error_text,
                    completed_at,
                    job_id,
                    room_id,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM world_memory_depth_jobs WHERE id = ? AND room_id = ?",
                (job_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def replace_world_memory_depth_results(
        self,
        *,
        job_id: int,
        room_id: str,
        results: list[Mapping[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            active_conn.execute(
                "DELETE FROM world_memory_depth_results WHERE job_id = ? AND room_id = ?",
                (job_id, room_id),
            )
            timestamp = utc_now_iso()
            for result in results:
                active_conn.execute(
                    """
                    INSERT INTO world_memory_depth_results (
                        job_id,
                        room_id,
                        node_id,
                        cluster_id,
                        asset_id,
                        label,
                        relative_path,
                        asset_kind,
                        renderer,
                        status,
                        source_image_path,
                        depth_preview_path,
                        depth_raw_path,
                        width_px,
                        height_px,
                        notes_json,
                        warnings_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        room_id,
                        result["node_id"],
                        result["cluster_id"],
                        result["asset_id"],
                        result["label"],
                        result["relative_path"],
                        result["asset_kind"],
                        result["renderer"],
                        result["status"],
                        result["source_image_path"],
                        result["depth_preview_path"],
                        result["depth_raw_path"],
                        result["width_px"],
                        result["height_px"],
                        json.dumps(list(result.get("notes", [])), sort_keys=True),
                        json.dumps(list(result.get("warnings", [])), sort_keys=True),
                        timestamp,
                        timestamp,
                    ),
                )
            rows = active_conn.execute(
                """
                SELECT *
                FROM world_memory_depth_results
                WHERE job_id = ? AND room_id = ?
                ORDER BY id ASC
                """,
                (job_id, room_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_world_memory_depth_jobs(self, *, room_id: str, limit: int = 12) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM world_memory_depth_jobs
                WHERE room_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (room_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_world_memory_depth_job(self, job_id: int, *, room_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM world_memory_depth_jobs
                WHERE id = ? AND room_id = ?
                """,
                (job_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_world_memory_depth_results(self, *, job_id: int, room_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM world_memory_depth_results
                WHERE job_id = ? AND room_id = ?
                ORDER BY id ASC
                """,
                (job_id, room_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def latest_world_memory_depth_result(self, *, node_id: str, room_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT r.*
                FROM world_memory_depth_results r
                JOIN world_memory_depth_jobs j ON j.id = r.job_id
                WHERE r.node_id = ? AND r.room_id = ? AND j.room_id = ? AND j.status = 'completed'
                ORDER BY r.updated_at DESC, r.id DESC
                LIMIT 1
                """,
                (node_id, room_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_ingest_runs(self, *, room_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT ir.*,
                       d.label AS dataset_label,
                       d.classification_level,
                       d.collection,
                       CASE WHEN irm.ingest_run_id IS NULL THEN 0 ELSE 1 END AS has_manifest
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                LEFT JOIN ingest_run_manifests irm ON irm.ingest_run_id = ir.id
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
                SELECT ir.*,
                       d.label AS dataset_label,
                       d.classification_level,
                       d.collection,
                       CASE WHEN irm.ingest_run_id IS NULL THEN 0 ELSE 1 END AS has_manifest
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                LEFT JOIN ingest_run_manifests irm ON irm.ingest_run_id = ir.id
                WHERE ir.room_id = ?
                ORDER BY ir.started_at DESC
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def get_ingest_run(
        self,
        run_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT ir.*,
                       d.label AS dataset_label,
                       d.classification_level,
                       d.collection,
                       CASE WHEN irm.ingest_run_id IS NULL THEN 0 ELSE 1 END AS has_manifest
                FROM ingest_runs ir
                JOIN datasets d ON d.id = ir.dataset_id
                LEFT JOIN ingest_run_manifests irm ON irm.ingest_run_id = ir.id
                WHERE ir.id = ? AND ir.room_id = ?
                """,
                (run_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def record_ingest_run_manifest(
        self,
        *,
        ingest_run_id: int,
        dataset_id: int,
        room_id: str,
        normalized_root_path: str,
        total_size_bytes: int,
        sample_limit: int,
        asset_kind_breakdown: list[Mapping[str, Any]],
        sample_assets: list[Mapping[str, Any]],
        warnings: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        with self._borrowed_connection(conn) as active_conn:
            created_at = utc_now_iso()
            active_conn.execute(
                """
                INSERT INTO ingest_run_manifests (
                    ingest_run_id,
                    dataset_id,
                    room_id,
                    normalized_root_path,
                    total_size_bytes,
                    sample_limit,
                    asset_kind_breakdown_json,
                    sample_assets_json,
                    warnings_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ingest_run_id) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    room_id = excluded.room_id,
                    normalized_root_path = excluded.normalized_root_path,
                    total_size_bytes = excluded.total_size_bytes,
                    sample_limit = excluded.sample_limit,
                    asset_kind_breakdown_json = excluded.asset_kind_breakdown_json,
                    sample_assets_json = excluded.sample_assets_json,
                    warnings_json = excluded.warnings_json
                """,
                (
                    ingest_run_id,
                    dataset_id,
                    room_id,
                    normalized_root_path,
                    total_size_bytes,
                    sample_limit,
                    json.dumps(asset_kind_breakdown, sort_keys=True),
                    json.dumps(sample_assets, sort_keys=True),
                    json.dumps(warnings, sort_keys=True),
                    created_at,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM ingest_run_manifests
                WHERE ingest_run_id = ?
                """,
                (ingest_run_id,),
            ).fetchone()
            return dict(row)

    def get_ingest_run_manifest(
        self,
        run_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT irm.*
                FROM ingest_run_manifests irm
                JOIN ingest_runs ir ON ir.id = irm.ingest_run_id
                WHERE irm.ingest_run_id = ? AND irm.room_id = ? AND ir.room_id = ?
                """,
                (run_id, room_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    # Audit queries
    def list_audit_events(
        self,
        *,
        room_id: str,
        limit: int = 25,
        offset: int = 0,
        event_type: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            clauses = ["room_id = ?"]
            params: list[Any] = [room_id]
            if event_type is not None:
                clauses.append("event_type = ?")
                params.append(event_type)
            if target_type is not None:
                clauses.append("target_type = ?")
                params.append(target_type)
            if target_id is not None:
                clauses.append("target_id = ?")
                params.append(target_id)
            rows = conn.execute(
                f"""
                SELECT *
                FROM audit_events
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_audit_events_by_ids(
        self,
        audit_event_ids: list[int],
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        if not audit_event_ids:
            return []
        placeholders = ", ".join("?" for _ in audit_event_ids)
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                f"""
                SELECT *
                FROM audit_events
                WHERE room_id = ?
                  AND id IN ({placeholders})
                ORDER BY created_at ASC, id ASC
                """,
                [room_id, *audit_event_ids],
            ).fetchall()
            return [dict(row) for row in rows]

    def list_audit_events_for_room(
        self,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT *
                FROM audit_events
                WHERE room_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (room_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_control_plane_audit_chain(self, *, limit: int = 25) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM control_plane_audit_chain
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    # Memory persistence
    def upsert_memory_event(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM memory_events
                WHERE room_id = ?
                  AND source_table = ?
                  AND source_record_id = ?
                  AND event_type = ?
                """,
                (
                    payload["room_id"],
                    payload["source_table"],
                    payload["source_record_id"],
                    payload["event_type"],
                ),
            ).fetchone()
            if existing is not None:
                return dict(existing), False

            metadata_json = self._encode_metadata(payload.get("metadata"))
            timestamp = utc_now_iso()
            cursor = active_conn.execute(
                """
                INSERT INTO memory_events (
                    room_id, classification_level, event_type, source_table, source_record_id,
                    dataset_id, asset_id, ingest_run_id, occurred_at, recorded_at, title,
                    evidence_text, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["room_id"],
                    payload["classification_level"],
                    payload["event_type"],
                    payload["source_table"],
                    payload["source_record_id"],
                    payload.get("dataset_id"),
                    payload.get("asset_id"),
                    payload.get("ingest_run_id"),
                    payload["occurred_at"],
                    payload["recorded_at"],
                    payload["title"],
                    payload["evidence_text"],
                    metadata_json,
                    payload.get("created_at", timestamp),
                    payload.get("updated_at", timestamp),
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM memory_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True

    def upsert_memory_entity(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM memory_entities
                WHERE room_id = ?
                  AND entity_type = ?
                  AND canonical_key = ?
                """,
                (
                    payload["room_id"],
                    payload["entity_type"],
                    payload["canonical_key"],
                ),
            ).fetchone()
            metadata_json = self._encode_metadata(payload.get("metadata"))
            timestamp = utc_now_iso()
            if existing is not None:
                first_seen_at = min(existing["first_seen_at"], payload["first_seen_at"])
                last_seen_at = max(existing["last_seen_at"], payload["last_seen_at"])
                active_conn.execute(
                    """
                    UPDATE memory_entities
                    SET classification_level = ?,
                        canonical_name = ?,
                        seed_source_event_id = ?,
                        first_seen_at = ?,
                        last_seen_at = ?,
                        metadata_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["classification_level"],
                        payload["canonical_name"],
                        payload["seed_source_event_id"],
                        first_seen_at,
                        last_seen_at,
                        metadata_json,
                        timestamp,
                        existing["id"],
                    ),
                )
                row = active_conn.execute(
                    "SELECT * FROM memory_entities WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                return dict(row), False

            cursor = active_conn.execute(
                """
                INSERT INTO memory_entities (
                    room_id, classification_level, entity_type, canonical_name, canonical_key,
                    seed_source_event_id, first_seen_at, last_seen_at, metadata_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["room_id"],
                    payload["classification_level"],
                    payload["entity_type"],
                    payload["canonical_name"],
                    payload["canonical_key"],
                    payload["seed_source_event_id"],
                    payload["first_seen_at"],
                    payload["last_seen_at"],
                    metadata_json,
                    payload.get("created_at", timestamp),
                    payload.get("updated_at", timestamp),
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM memory_entities WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True

    def upsert_memory_episode(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                "SELECT * FROM memory_episodes WHERE id = ?",
                (payload["id"],),
            ).fetchone()
            metadata_json = self._encode_metadata(payload.get("metadata"))
            timestamp = utc_now_iso()
            if existing is not None:
                active_conn.execute(
                    """
                    UPDATE memory_episodes
                    SET classification_level = ?,
                        grouping_basis = ?,
                        title = ?,
                        summary = ?,
                        start_at = ?,
                        end_at = ?,
                        metadata_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["classification_level"],
                        payload["grouping_basis"],
                        payload["title"],
                        payload["summary"],
                        payload["start_at"],
                        payload["end_at"],
                        metadata_json,
                        timestamp,
                        payload["id"],
                    ),
                )
                row = active_conn.execute(
                    "SELECT * FROM memory_episodes WHERE id = ?",
                    (payload["id"],),
                ).fetchone()
                return dict(row), False

            active_conn.execute(
                """
                INSERT INTO memory_episodes (
                    id, room_id, classification_level, episode_type, grouping_basis,
                    source_table, source_record_id, title, summary, start_at, end_at,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["room_id"],
                    payload["classification_level"],
                    payload["episode_type"],
                    payload["grouping_basis"],
                    payload["source_table"],
                    payload["source_record_id"],
                    payload["title"],
                    payload["summary"],
                    payload["start_at"],
                    payload["end_at"],
                    metadata_json,
                    payload.get("created_at", timestamp),
                    payload.get("updated_at", timestamp),
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM memory_episodes WHERE id = ?",
                (payload["id"],),
            ).fetchone()
            return dict(row), True

    def upsert_memory_event_entity_link(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM memory_event_entities
                WHERE event_id = ? AND entity_id = ? AND role = ?
                """,
                (
                    payload["event_id"],
                    payload["entity_id"],
                    payload["role"],
                ),
            ).fetchone()
            if existing is not None:
                return dict(existing), False

            created_at = payload.get("created_at", utc_now_iso())
            active_conn.execute(
                """
                INSERT INTO memory_event_entities (event_id, entity_id, role, source_basis, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload["entity_id"],
                    payload["role"],
                    payload["source_basis"],
                    created_at,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_event_entities
                WHERE event_id = ? AND entity_id = ? AND role = ?
                """,
                (
                    payload["event_id"],
                    payload["entity_id"],
                    payload["role"],
                ),
            ).fetchone()
            return dict(row), True

    def upsert_memory_episode_event_link(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM memory_episode_events
                WHERE episode_id = ? AND event_id = ?
                """,
                (
                    payload["episode_id"],
                    payload["event_id"],
                ),
            ).fetchone()
            if existing is not None:
                return dict(existing), False

            created_at = payload.get("created_at", utc_now_iso())
            active_conn.execute(
                """
                INSERT INTO memory_episode_events (
                    episode_id, event_id, sequence_no, inclusion_basis, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["episode_id"],
                    payload["event_id"],
                    payload["sequence_no"],
                    payload["inclusion_basis"],
                    created_at,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_episode_events
                WHERE episode_id = ? AND event_id = ?
                """,
                (
                    payload["episode_id"],
                    payload["event_id"],
                ),
            ).fetchone()
            return dict(row), True

    def upsert_memory_provenance(
        self,
        payload: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._borrowed_connection(conn) as active_conn:
            existing = active_conn.execute(
                """
                SELECT *
                FROM memory_provenance
                WHERE room_id = ?
                  AND owner_type = ?
                  AND owner_id = ?
                  AND provenance_type = ?
                  AND source_table = ?
                  AND source_record_id = ?
                  AND ((source_field = ?) OR (source_field IS NULL AND ? IS NULL))
                  AND basis_type = ?
                  AND ((basis_value = ?) OR (basis_value IS NULL AND ? IS NULL))
                """,
                (
                    payload["room_id"],
                    payload["owner_type"],
                    payload["owner_id"],
                    payload["provenance_type"],
                    payload["source_table"],
                    payload["source_record_id"],
                    payload.get("source_field"),
                    payload.get("source_field"),
                    payload["basis_type"],
                    payload.get("basis_value"),
                    payload.get("basis_value"),
                ),
            ).fetchone()
            if existing is not None:
                return dict(existing), False

            created_at = payload.get("created_at", utc_now_iso())
            cursor = active_conn.execute(
                """
                INSERT INTO memory_provenance (
                    room_id, owner_type, owner_id, provenance_type, source_table,
                    source_record_id, source_field, basis_type, basis_value, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["room_id"],
                    payload["owner_type"],
                    payload["owner_id"],
                    payload["provenance_type"],
                    payload["source_table"],
                    payload["source_record_id"],
                    payload.get("source_field"),
                    payload["basis_type"],
                    payload.get("basis_value"),
                    created_at,
                ),
            )
            row = active_conn.execute(
                "SELECT * FROM memory_provenance WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row), True

    def list_memory_provenance(
        self,
        *,
        room_id: str,
        owner_type: str,
        owner_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT *
                FROM memory_provenance
                WHERE room_id = ?
                  AND owner_type = ?
                  AND owner_id = ?
                ORDER BY provenance_type ASC, source_table ASC, source_record_id ASC, basis_type ASC, id ASC
                """,
                (room_id, owner_type, owner_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_events(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: MemoryStatus | None = None,
        event_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            clauses = ["room_id = ?"]
            params: list[Any] = [room_id]
            if status is not None:
                clauses.append("status = ?")
                params.append(status)
            elif not include_corrected:
                clauses.append("status = ?")
                params.append("active")
            if event_type is not None:
                clauses.append("event_type = ?")
                params.append(event_type)
            if ingest_run_id is not None:
                clauses.append("ingest_run_id = ?")
                params.append(ingest_run_id)
            rows = conn.execute(
                f"""
                SELECT *
                FROM memory_events
                WHERE {' AND '.join(clauses)}
                ORDER BY occurred_at DESC, created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_memory_event(
        self,
        event_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_events
                WHERE id = ? AND room_id = ?
                """,
                (event_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def get_memory_event_for_correction(
        self,
        event_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        return self.get_memory_event(event_id, room_id=room_id, conn=conn)

    def set_event_status(
        self,
        room_id: str,
        event_id: int,
        status: MemoryStatus,
        reason: str | None,
        actor_role: str | None,
        *,
        superseded_by_id: int | None = None,
        corrected_at: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        self._validate_memory_status(status=status, superseded_by_id=superseded_by_id)
        with self._borrowed_connection(conn) as active_conn:
            existing_row = self.get_memory_event(event_id, room_id=room_id, conn=active_conn)
            if existing_row is None:
                return None
            effective_corrected_at = corrected_at or existing_row.get("corrected_at") or utc_now_iso()
            if (
                existing_row["status"] == status
                and existing_row.get("correction_reason") == reason
                and existing_row.get("superseded_by_id") == superseded_by_id
                and existing_row.get("corrected_by_role") == actor_role
            ):
                return existing_row
            active_conn.execute(
                """
                UPDATE memory_events
                SET status = ?,
                    correction_reason = ?,
                    superseded_by_id = ?,
                    corrected_at = ?,
                    corrected_by_role = ?,
                    updated_at = ?
                WHERE id = ? AND room_id = ?
                """,
                (
                    status,
                    reason,
                    superseded_by_id,
                    effective_corrected_at,
                    actor_role,
                    utc_now_iso(),
                    event_id,
                    room_id,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_events
                WHERE id = ? AND room_id = ?
                """,
                (event_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def update_memory_event_status(
        self,
        event_id: int,
        *,
        room_id: str,
        status: MemoryStatus,
        correction_reason: str | None,
        superseded_by_id: int | None,
        corrected_at: str | None,
        corrected_by_role: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        return self.set_event_status(
            room_id=room_id,
            event_id=event_id,
            status=status,
            reason=correction_reason,
            actor_role=corrected_by_role,
            superseded_by_id=superseded_by_id,
            corrected_at=corrected_at,
            conn=conn,
        )

    def validate_same_room_event_reference(
        self,
        *,
        room_id: str,
        event_id: int,
        reference_event_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        source_event = self.get_memory_event(event_id, room_id=room_id, conn=conn)
        referenced_event = self.get_memory_event(reference_event_id, room_id=room_id, conn=conn)
        if source_event is None or referenced_event is None:
            return None
        return referenced_event

    def link_supersession(
        self,
        room_id: str,
        old_event_id: int,
        new_event_id: int,
        reason: str | None,
        actor_role: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        if old_event_id == new_event_id:
            raise ValueError("A memory event cannot supersede itself.")
        with self._borrowed_connection(conn) as active_conn:
            old_event = self.get_memory_event(old_event_id, room_id=room_id, conn=active_conn)
            new_event = self.get_memory_event(new_event_id, room_id=room_id, conn=active_conn)
            if old_event is None:
                raise ValueError(f"Memory event {old_event_id} was not found in room {room_id}.")
            if new_event is None:
                raise ValueError(f"Replacement memory event {new_event_id} was not found in room {room_id}.")

            existing_row = active_conn.execute(
                """
                SELECT *
                FROM memory_event_supersessions
                WHERE room_id = ? AND old_event_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (room_id, str(old_event_id)),
            ).fetchone()
            if existing_row is not None:
                payload = dict(existing_row)
                if payload["new_event_id"] != str(new_event_id):
                    raise ValueError("Memory event is already superseded by a different replacement event.")
                return payload

            supersession_id = f"memory_event_supersession:{room_id}:{old_event_id}:{new_event_id}"
            created_at = utc_now_iso()
            active_conn.execute(
                """
                INSERT INTO memory_event_supersessions (
                    id,
                    room_id,
                    old_event_id,
                    new_event_id,
                    reason,
                    created_at,
                    created_by_role
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(room_id, old_event_id, new_event_id) DO NOTHING
                """,
                (
                    supersession_id,
                    room_id,
                    str(old_event_id),
                    str(new_event_id),
                    reason,
                    created_at,
                    actor_role,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_event_supersessions
                WHERE room_id = ? AND old_event_id = ? AND new_event_id = ?
                """,
                (room_id, str(old_event_id), str(new_event_id)),
            ).fetchone()
            return dict(row)

    def list_memory_event_entity_details(
        self,
        event_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT me.entity_id,
                       e.room_id,
                       e.classification_level,
                       e.entity_type,
                       e.canonical_name,
                       e.canonical_key,
                       e.first_seen_at,
                       e.last_seen_at,
                       me.role,
                       me.source_basis,
                       e.metadata_json
                FROM memory_event_entities me
                JOIN memory_entities e ON e.id = me.entity_id
                JOIN memory_events ev ON ev.id = me.event_id
                WHERE me.event_id = ?
                  AND ev.room_id = ?
                  AND e.room_id = ?
                ORDER BY e.entity_type ASC, e.canonical_key ASC, me.role ASC
                """,
                (event_id, room_id, room_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_events_for_ingest_run(
        self,
        *,
        room_id: str,
        ingest_run_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT *
                FROM memory_events
                WHERE room_id = ? AND ingest_run_id = ?
                ORDER BY occurred_at ASC, recorded_at ASC, id ASC
                """,
                (room_id, ingest_run_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_entities(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM memory_entities
                WHERE room_id = ?
                ORDER BY last_seen_at DESC, canonical_name ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (room_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_memory_entity(self, entity_id: int, *, room_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM memory_entities
                WHERE id = ? AND room_id = ?
                """,
                (entity_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_memory_episodes(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: MemoryStatus | None = None,
        episode_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            clauses = ["room_id = ?"]
            params: list[Any] = [room_id]
            if status is not None:
                clauses.append("status = ?")
                params.append(status)
            elif not include_corrected:
                clauses.append("status = ?")
                params.append("active")
            if episode_type is not None:
                clauses.append("episode_type = ?")
                params.append(episode_type)
            if ingest_run_id is not None:
                clauses.append("source_table = ?")
                clauses.append("source_record_id = ?")
                params.extend(["ingest_runs", str(ingest_run_id)])
            rows = conn.execute(
                f"""
                SELECT *
                FROM memory_episodes
                WHERE {' AND '.join(clauses)}
                ORDER BY start_at DESC, created_at DESC, id ASC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_memory_episode(
        self,
        episode_id: str,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        with self._borrowed_connection(conn) as active_conn:
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_episodes
                WHERE id = ? AND room_id = ?
                """,
                (episode_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def get_memory_episode_for_correction(
        self,
        episode_id: str,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        return self.get_memory_episode(episode_id, room_id=room_id, conn=conn)

    def set_episode_status(
        self,
        room_id: str,
        episode_id: str,
        status: MemoryStatus,
        reason: str | None,
        actor_role: str | None,
        *,
        corrected_at: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        if status not in MEMORY_STATUS_VALUES:
            raise ValueError(f"Unsupported memory status: {status}")
        with self._borrowed_connection(conn) as active_conn:
            existing_row = self.get_memory_episode(episode_id, room_id=room_id, conn=active_conn)
            if existing_row is None:
                return None
            effective_corrected_at = corrected_at or existing_row.get("corrected_at") or utc_now_iso()
            if (
                existing_row["status"] == status
                and existing_row.get("correction_reason") == reason
                and existing_row.get("corrected_by_role") == actor_role
            ):
                return existing_row
            active_conn.execute(
                """
                UPDATE memory_episodes
                SET status = ?,
                    correction_reason = ?,
                    corrected_at = ?,
                    corrected_by_role = ?,
                    updated_at = ?
                WHERE id = ? AND room_id = ?
                """,
                (
                    status,
                    reason,
                    effective_corrected_at,
                    actor_role,
                    utc_now_iso(),
                    episode_id,
                    room_id,
                ),
            )
            row = active_conn.execute(
                """
                SELECT *
                FROM memory_episodes
                WHERE id = ? AND room_id = ?
                """,
                (episode_id, room_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def update_memory_episode_status(
        self,
        episode_id: str,
        *,
        room_id: str,
        status: MemoryStatus,
        correction_reason: str | None,
        corrected_at: str | None,
        corrected_by_role: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        return self.set_episode_status(
            room_id=room_id,
            episode_id=episode_id,
            status=status,
            reason=correction_reason,
            actor_role=corrected_by_role,
            corrected_at=corrected_at,
            conn=conn,
        )

    def list_memory_episode_events(
        self,
        episode_id: str,
        *,
        room_id: str,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT me.*
                FROM memory_episode_events mee
                JOIN memory_events me ON me.id = mee.event_id
                WHERE mee.episode_id = ? AND me.room_id = ?
                ORDER BY mee.sequence_no ASC, me.id ASC
                LIMIT ? OFFSET ?
                """,
                (episode_id, room_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_episode_member_details(
        self,
        episode_id: str,
        *,
        room_id: str,
        limit: int,
        offset: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT mee.sequence_no,
                       mee.inclusion_basis,
                       me.*
                FROM memory_episode_events mee
                JOIN memory_events me ON me.id = mee.event_id
                JOIN memory_episodes ep ON ep.id = mee.episode_id
                WHERE mee.episode_id = ?
                  AND ep.room_id = ?
                  AND me.room_id = ?
                ORDER BY mee.sequence_no ASC, me.id ASC
                LIMIT ? OFFSET ?
                """,
                (episode_id, room_id, room_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_event_episode_memberships(
        self,
        event_id: int,
        *,
        room_id: str,
        limit: int,
        offset: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT mee.sequence_no,
                       mee.inclusion_basis,
                       ep.id AS episode_id,
                       ep.room_id AS episode_room_id,
                       ep.classification_level AS episode_classification_level,
                       ep.episode_type,
                       ep.grouping_basis,
                       ep.source_table AS episode_source_table,
                       ep.source_record_id AS episode_source_record_id,
                       ep.title AS episode_title,
                       ep.summary AS episode_summary,
                       ep.status AS episode_status,
                       ep.correction_reason AS episode_correction_reason,
                       ep.corrected_at AS episode_corrected_at,
                       ep.corrected_by_role AS episode_corrected_by_role,
                       ep.start_at,
                       ep.end_at,
                       ep.metadata_json AS episode_metadata_json,
                       ep.created_at AS episode_created_at,
                       ep.updated_at AS episode_updated_at
                FROM memory_episode_events mee
                JOIN memory_episodes ep ON ep.id = mee.episode_id
                JOIN memory_events ev ON ev.id = mee.event_id
                WHERE mee.event_id = ?
                  AND ev.room_id = ?
                  AND ep.room_id = ?
                ORDER BY ep.start_at DESC, ep.created_at DESC, ep.id ASC, mee.sequence_no ASC
                LIMIT ? OFFSET ?
                """,
                (event_id, room_id, room_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_memory_event_supersession_relationships(
        self,
        event_id: int,
        *,
        room_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with self._borrowed_connection(conn) as active_conn:
            rows = active_conn.execute(
                """
                SELECT id,
                       room_id,
                       old_event_id,
                       new_event_id,
                       reason,
                       created_at,
                       created_by_role,
                       CASE
                           WHEN old_event_id = ? THEN 'old_event'
                           ELSE 'new_event'
                       END AS event_role
                FROM memory_event_supersessions
                WHERE room_id = ?
                  AND (old_event_id = ? OR new_event_id = ?)
                ORDER BY created_at ASC, id ASC
                """,
                (str(event_id), room_id, str(event_id), str(event_id)),
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
