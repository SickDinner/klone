"""Offline consistent SQLite backup for the local Android KLONE profile.

Run while KLONE is stopped for simplest recovery. SQLite's online backup API
also supports a consistent snapshot while the application is running.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import sys


def main() -> int:
    home = Path.home()
    data = Path(os.environ.get("KLONE_DATA_DIR", str(home / ".local/share/klone"))).expanduser()
    source = Path(os.environ.get("KLONE_DB_PATH", str(data / "klone_mission_control.db"))).expanduser()
    backup_dir = data / "backups"
    if not source.is_file():
        print(f"No database to back up: {source}", file=sys.stderr)
        return 2
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"klone-{stamp}.sqlite3"
    if target.exists():
        print("Backup target already exists; retry later", file=sys.stderr)
        return 2
    old_umask = os.umask(0o077)
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=10) as original:
            with sqlite3.connect(target, timeout=10) as destination:
                original.backup(destination)
                check = destination.execute("PRAGMA quick_check").fetchone()[0]
                if check != "ok":
                    raise RuntimeError("backup_integrity_check_failed")
        os.chmod(target, 0o600)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    finally:
        os.umask(old_umask)
    print(f"Verified local backup: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
