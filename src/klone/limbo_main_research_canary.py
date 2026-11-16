"""Isolated read-only E6 viewer of an existing main KLONE database.

Runs as a separate localhost canary. No KLONE main startup/bootstrap,
no SQLite writes and no routes that allow writes. The port-8000 service
continues uninterrupted; only the public research-room is consulted.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from fastapi import FastAPI, HTTPException, Query

from .limbo_intelligence import analyze
from .limbo_memory_bridge import recall


def _db() -> Path:
    raw=os.environ.get("KLONE_MAIN_RESEARCH_DB")
    if not raw:
        raise ValueError("KLONE_MAIN_RESEARCH_DB must identify an existing main database")
    path=Path(raw).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("main memory must be a non-symlink regular database")
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError("main memory must be a regular single-link file")
    return path


app=FastAPI(
    title="KLONE main public research memory (read-only)",
    docs_url=None,redoc_url=None,openapi_url=None,
)


@app.get("/health")
def health():
    try:
        db=_db()
    except ValueError as error:
        raise HTTPException(status_code=503,detail=str(error)) from error
    return {"status":"ok","service":"klone-main-research-readonly",
            "database_path":str(db),
            "room_scope":"research-room","read_only":True}


@app.get("/api/limbo-atlas/intelligence")
def intelligence(
    q: str = Query(...,min_length=3,max_length=160),
    limit: int = Query(default=24,ge=1,le=48),
    ring: int | None = Query(default=None,ge=2,le=8),
):
    try:
        return analyze(_db(),q,limit=limit,target_ring=ring)
    except (ValueError,PermissionError) as error:
        raise HTTPException(status_code=422,detail=str(error)) from error


@app.get("/api/limbo-atlas/memory/recall")
def memory_recall(
    q: str = Query(...,min_length=2,max_length=160),
    limit: int = Query(default=12,ge=1,le=30),
):
    try:
        return recall(_db(),q,limit=limit)
    except (ValueError,PermissionError) as error:
        raise HTTPException(status_code=422,detail=str(error)) from error
