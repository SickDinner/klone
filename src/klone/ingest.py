from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any

from .audit import AuditService
from .contracts import AssetKind, ClassificationLevel, IngestStatus
from .guards import access_guard, classification_guard
from .memory import MemoryService
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import DatasetIngestRequest


SKIPPED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}

IMAGE_EXTENSIONS = {".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
TEXT_EXTENSIONS = {".csv", ".html", ".htm", ".json", ".md", ".rtf", ".tsv", ".txt", ".xml", ".yaml", ".yml"}
DOCUMENT_EXTENSIONS = {".doc", ".docx", ".epub", ".odt", ".pdf", ".ppt", ".pptx", ".xls", ".xlsx"}
ARCHIVE_EXTENSIONS = {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"}
ASSET_KIND_ORDER: tuple[AssetKind, ...] = ("image", "audio", "video", "text", "document", "archive", "generic")

def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def classify_asset(path: Path) -> tuple[AssetKind, str | None]:
    extension = path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(path.name)
    if extension in IMAGE_EXTENSIONS or (mime_type and mime_type.startswith("image/")):
        return "image", mime_type or "image/unknown"
    if extension in AUDIO_EXTENSIONS or (mime_type and mime_type.startswith("audio/")):
        return "audio", mime_type or "audio/unknown"
    if extension in VIDEO_EXTENSIONS or (mime_type and mime_type.startswith("video/")):
        return "video", mime_type or "video/unknown"
    if extension in TEXT_EXTENSIONS or (mime_type and mime_type.startswith("text/")):
        return "text", mime_type or "text/plain"
    if extension in DOCUMENT_EXTENSIONS:
        return "document", mime_type or "application/octet-stream"
    if extension in ARCHIVE_EXTENSIONS:
        return "archive", mime_type or "application/octet-stream"
    return "generic", mime_type or "application/octet-stream"


def iter_files(root_path: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    errors: list[str] = []

    def handle_error(error: OSError) -> None:
        errors.append(str(error))

    for current_root, directories, file_names in os.walk(
        root_path,
        onerror=handle_error,
        followlinks=False,
    ):
        directories[:] = [
            directory
            for directory in directories
            if directory not in SKIPPED_DIRECTORIES
            and not Path(current_root, directory).is_symlink()
        ]
        for file_name in file_names:
            candidate = Path(current_root, file_name)
            if candidate.is_symlink():
                continue
            files.append(candidate)

    return files, errors


def build_asset_payload(
    file_path: Path,
    *,
    root_path: Path,
    collection: str,
    classification_level: ClassificationLevel,
) -> dict[str, Any]:
    stat = file_path.stat()
    asset_kind, mime_type = classify_asset(file_path)
    indexed_at = datetime.now(UTC).isoformat()
    room_id = room_registry.default_room_for_classification(classification_level).id
    return {
        "room_id": room_id,
        "path": str(file_path),
        "relative_path": str(file_path.relative_to(root_path)),
        "file_name": file_path.name,
        "extension": file_path.suffix.lower(),
        "size_bytes": stat.st_size,
        "sha256": sha256_for_file(file_path),
        "mime_type": mime_type,
        "asset_kind": asset_kind,
        "classification_level": classification_level,
        "extraction_status": "metadata_indexed",
        "fs_created_at": iso_from_timestamp(stat.st_ctime),
        "fs_modified_at": iso_from_timestamp(stat.st_mtime),
        "indexed_at": indexed_at,
        "collection": collection,
        "metadata": {
            "source": "recursive_file_scan",
            "root_path": str(root_path),
            "sanitized_summary": f"{asset_kind} asset {file_path.name}",
        },
    }


def preview_ingest_manifest(
    repository: KloneRepository,
    request: DatasetIngestRequest,
    *,
    sample_limit: int = 12,
) -> dict[str, Any]:
    root_path = normalize_root_path(request.root_path)
    files, walk_errors = iter_files(root_path)
    room = room_registry.default_room_for_classification(request.classification_level)
    room_id = room.id
    classification_decision = classification_guard.evaluate(
        classification_level=request.classification_level,
        room_id=room_id,
    )
    access_decision = access_guard.evaluate(
        room_id=room_id,
        actor_role="owner",
        requested_permission="write",
    )

    sorted_files = sorted(files, key=lambda item: str(item.relative_to(root_path)).lower())
    existing_dataset: dict[str, Any] | None = None
    total_size_bytes = 0
    planned_new_assets = 0
    planned_updated_assets = 0
    planned_unchanged_assets = 0
    duplicates_detected = 0
    kind_breakdown: dict[AssetKind, dict[str, int]] = {
        asset_kind: {"count": 0, "total_size_bytes": 0}
        for asset_kind in ASSET_KIND_ORDER
    }
    sample_assets: list[dict[str, Any]] = []

    with repository.connection() as conn:
        existing_dataset = repository.get_dataset_by_root_path(str(root_path), conn=conn)
        existing_dataset_id = existing_dataset["id"] if existing_dataset is not None else None
        for file_path in sorted_files:
            asset_payload = build_asset_payload(
                file_path,
                root_path=root_path,
                collection=request.collection,
                classification_level=request.classification_level,
            )
            total_size_bytes += int(asset_payload["size_bytes"])
            asset_kind = asset_payload["asset_kind"]
            kind_breakdown[asset_kind]["count"] += 1
            kind_breakdown[asset_kind]["total_size_bytes"] += int(asset_payload["size_bytes"])

            existing_asset = (
                repository.get_asset_by_dataset_path(
                    existing_dataset_id,
                    path=str(asset_payload["path"]),
                    conn=conn,
                )
                if existing_dataset_id is not None
                else None
            )
            canonical = repository.find_duplicate_asset_candidate(
                sha256=str(asset_payload["sha256"]),
                dataset_id=existing_dataset_id,
                path=str(asset_payload["path"]),
                conn=conn,
            )
            dedup_status = "duplicate" if canonical is not None else "unique"
            planned_action = "new"
            if existing_asset is not None:
                planned_action = "updated" if existing_asset["sha256"] != asset_payload["sha256"] else "unchanged"

            if planned_action == "new":
                planned_new_assets += 1
            elif planned_action == "updated":
                planned_updated_assets += 1
            else:
                planned_unchanged_assets += 1
            if dedup_status == "duplicate":
                duplicates_detected += 1

            if len(sample_assets) < sample_limit:
                sample_assets.append(
                    {
                        "relative_path": asset_payload["relative_path"],
                        "file_name": asset_payload["file_name"],
                        "asset_kind": asset_kind,
                        "mime_type": asset_payload["mime_type"],
                        "size_bytes": asset_payload["size_bytes"],
                        "planned_action": planned_action,
                        "dedup_status": dedup_status,
                        "canonical_asset_id": canonical["id"] if canonical is not None else None,
                        "canonical_dataset_label": canonical["dataset_label"] if canonical is not None else None,
                        "canonical_relative_path": canonical["relative_path"] if canonical is not None else None,
                    }
                )

    warnings = list(walk_errors)
    if classification_decision.decision != "allowed":
        warnings.append(classification_decision.reason)
    if access_decision.decision != "allowed":
        warnings.append(access_decision.reason)

    asset_kind_breakdown = [
        {
            "asset_kind": asset_kind,
            "count": summary["count"],
            "total_size_bytes": summary["total_size_bytes"],
        }
        for asset_kind, summary in kind_breakdown.items()
        if summary["count"] > 0
    ]

    return {
        "request": request.model_dump(mode="json"),
        "normalized_root_path": str(root_path),
        "room_id": room.id,
        "room_label": room.label,
        "existing_dataset_id": existing_dataset["id"] if existing_dataset is not None else None,
        "existing_dataset_slug": existing_dataset["slug"] if existing_dataset is not None else None,
        "classification_guard": classification_decision.model_dump(mode="json"),
        "access_guard": access_decision.model_dump(mode="json"),
        "can_start_ingest": (
            classification_decision.decision == "allowed"
            and access_decision.decision == "allowed"
        ),
        "files_discovered": len(sorted_files),
        "total_size_bytes": total_size_bytes,
        "planned_new_assets": planned_new_assets,
        "planned_updated_assets": planned_updated_assets,
        "planned_unchanged_assets": planned_unchanged_assets,
        "duplicates_detected": duplicates_detected,
        "asset_kind_breakdown": asset_kind_breakdown,
        "sample_limit": sample_limit,
        "sample_assets": sample_assets,
        "warnings": warnings,
    }


def normalize_root_path(raw_root_path: str) -> Path:
    root_path = Path(raw_root_path).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Dataset root does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Dataset root is not a directory: {root_path}")
    return root_path


def ingest_dataset(
    repository: KloneRepository,
    request: DatasetIngestRequest,
    *,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    root_path = normalize_root_path(request.root_path)
    files, walk_errors = iter_files(root_path)
    room = room_registry.default_room_for_classification(request.classification_level)
    room_id = room.id

    with repository.connection() as conn:
        audit_service = AuditService(repository)
        memory_service = MemoryService(repository)
        memory_source_event_ids: list[int] = []

        ingest_requested_event = audit_service.log_event(
            event_type="ingest_requested",
            actor="hypervisor",
            target_type="dataset_root",
            target_id=str(root_path),
            room_id=room_id,
            classification_level=request.classification_level,
            summary=f"Ingest requested for '{request.label}'.",
            metadata={
                "root_path": str(root_path),
                "collection": request.collection,
                "classification_level": request.classification_level,
            },
            conn=conn,
        )
        memory_source_event_ids.append(ingest_requested_event.id)
        classification_decision = classification_guard.evaluate(
            classification_level=request.classification_level,
            room_id=room_id,
        )
        if classification_decision.decision != "allowed":
            ingest_blocked_event = audit_service.log_event(
                event_type="ingest_blocked",
                actor="hypervisor",
                target_type="dataset_root",
                target_id=str(root_path),
                room_id=room_id,
                classification_level=request.classification_level,
                summary="Ingest blocked by ClassificationGuard.",
                metadata=classification_decision.model_dump(),
                conn=conn,
            )
            memory_source_event_ids.append(ingest_blocked_event.id)
            memory_service.seed_from_audit_events(
                room_id=room_id,
                audit_event_ids=memory_source_event_ids,
                conn=conn,
            )
            raise PermissionError(classification_decision.reason)
        access_decision = access_guard.evaluate(
            room_id=room_id,
            actor_role="owner",
            requested_permission="write",
        )
        if access_decision.decision not in {"allowed", "requires_approval"}:
            ingest_blocked_event = audit_service.log_event(
                event_type="ingest_blocked",
                actor="hypervisor",
                target_type="dataset_root",
                target_id=str(root_path),
                room_id=room_id,
                classification_level=request.classification_level,
                summary="Ingest blocked by AccessGuard.",
                metadata=access_decision.model_dump(),
                conn=conn,
            )
            memory_source_event_ids.append(ingest_blocked_event.id)
            memory_service.seed_from_audit_events(
                room_id=room_id,
                audit_event_ids=memory_source_event_ids,
                conn=conn,
            )
            raise PermissionError(access_decision.reason)

        dataset, created = repository.upsert_dataset(
            label=request.label,
            root_path=str(root_path),
            room_id=room_id,
            collection=request.collection,
            classification_level=request.classification_level,
            description=request.description,
            conn=conn,
        )
        dataset_event = audit_service.log_event(
            event_type="dataset_registered" if created else "dataset_updated",
            actor="hypervisor",
            target_type="dataset",
            target_id=str(dataset["id"]),
            room_id=room_id,
            classification_level=request.classification_level,
            summary=f"Dataset '{dataset['label']}' registered for ingest.",
            metadata={
                "dataset_id": dataset["id"],
                "collection": request.collection,
                "description": request.description,
                "root_path": str(root_path),
            },
            conn=conn,
        )
        memory_source_event_ids.append(dataset_event.id)

        run = repository.start_ingest_run(
            dataset["id"],
            room_id=room_id,
            trigger_source=trigger_source,
            conn=conn,
        )
        repository.mark_dataset_scan_state(
            dataset["id"],
            scan_state="running",
            last_scan_at=run["started_at"],
            conn=conn,
        )
        ingest_started_event = audit_service.log_event(
            event_type="ingest_started",
            actor="hypervisor",
            target_type="ingest_run",
            target_id=str(run["id"]),
            room_id=room_id,
            classification_level=request.classification_level,
            summary=f"Ingest started for dataset '{dataset['label']}'.",
            metadata={
                "dataset_id": dataset["id"],
                "ingest_run_id": run["id"],
                "files_discovered": len(files),
            },
            conn=conn,
        )
        memory_source_event_ids.append(ingest_started_event.id)

        assets_indexed = 0
        new_assets = 0
        updated_assets = 0
        unchanged_assets = 0
        duplicates_detected = 0
        errors_detected = len(walk_errors)

        for file_path in files:
            try:
                asset_payload = build_asset_payload(
                    file_path,
                    root_path=root_path,
                    collection=request.collection,
                    classification_level=request.classification_level,
                )
                result = repository.upsert_asset(
                    dataset["id"],
                    run["id"],
                    asset_payload,
                    conn=conn,
                )
                assets_indexed += 1
                if result["action"] == "new":
                    new_assets += 1
                elif result["action"] == "updated":
                    updated_assets += 1
                else:
                    unchanged_assets += 1
                if result["is_duplicate"]:
                    duplicates_detected += 1
            except OSError as error:
                errors_detected += 1
                walk_errors.append(f"{file_path}: {error}")

        summary = (
            f"Indexed {assets_indexed} assets from {len(files)} discovered files; "
            f"{duplicates_detected} duplicates flagged and {errors_detected} errors observed."
        )
        final_status: IngestStatus = (
            "completed" if errors_detected == 0 else "completed_with_warnings"
        )
        completed_run = repository.finish_ingest_run(
            run["id"],
            status=final_status,
            files_discovered=len(files),
            assets_indexed=assets_indexed,
            new_assets=new_assets,
            updated_assets=updated_assets,
            unchanged_assets=unchanged_assets,
            duplicates_detected=duplicates_detected,
            errors_detected=errors_detected,
            summary=summary,
            conn=conn,
        )
        repository.mark_dataset_scan_state(
            dataset["id"],
            scan_state=final_status,
            last_scan_at=completed_run["completed_at"],
            conn=conn,
        )
        ingest_completed_event = audit_service.log_event(
            event_type="ingest_completed",
            actor="hypervisor",
            target_type="ingest_run",
            target_id=str(completed_run["id"]),
            room_id=room_id,
            classification_level=request.classification_level,
            summary=f"Ingest finished for dataset '{dataset['label']}'.",
            metadata={
                "dataset_id": dataset["id"],
                "ingest_run_id": completed_run["id"],
                "files_discovered": len(files),
                "assets_indexed": assets_indexed,
                "new_assets": new_assets,
                "updated_assets": updated_assets,
                "unchanged_assets": unchanged_assets,
                "duplicates_detected": duplicates_detected,
                "errors": walk_errors[-10:],
            },
            conn=conn,
        )
        memory_source_event_ids.append(ingest_completed_event.id)
        memory_service.seed_from_audit_events(
            room_id=room_id,
            audit_event_ids=memory_source_event_ids,
            ingest_run_id=completed_run["id"],
            conn=conn,
        )

    datasets = repository.list_datasets(room_id=room_id)
    refreshed_dataset = next(item for item in datasets if item["id"] == dataset["id"])
    return {
        "dataset": refreshed_dataset,
        "run": completed_run,
        "errors": walk_errors,
    }
