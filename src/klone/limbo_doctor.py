"""KLONE Doctor E10: localhost + SQLite read-only fault isolation for Termux.

Fixed loopback endpoints, no redirects, no external network, no restarts,
no schema bootstrap, no DB writes. Only output is an opt-in diagnostic JSON.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import stat
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from .evidence_io import write_new_report

SERVICES=(
    ("main","http://127.0.0.1:8000/api/health"),
    ("atlas","http://127.0.0.1:8031/api/health"),
    ("research","http://127.0.0.1:8041/health"),
)
MAX_HEALTH_BYTES=16384


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("unexpected redirect from localhost service")


def _read_health(url,*,opener=None):
    # Literal whitelist of local destinations; never follow a server-provided URL.
    if url not in {u for _,u in SERVICES}:
        raise ValueError("non-whitelisted diagnostics endpoint")
    client=opener if opener is not None else build_opener(ProxyHandler({}),_NoRedirect())
    with client.open(url,timeout=3) as res:
        if res.status!=200:
            raise ValueError("health status is not HTTP 200")
        content=res.read(MAX_HEALTH_BYTES+1)
    if len(content)>MAX_HEALTH_BYTES:
        raise ValueError("health response size limit exceeded")
    data=json.loads(content)
    if not isinstance(data,dict):
        raise ValueError("health response is not a JSON object")
    return data


def _validate_file(path,expected):
    path=Path(path)
    expected=Path(expected)
    if path!=expected or path.is_symlink() or not path.is_file():
        raise ValueError("main database differs from the expected original file")
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError("main database is not a regular single-link file")
    return path


def _inspect_db(path):
    # URI mode=ro does not initialize, migrate or create missing files.
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=5)) as conn:
        quick=conn.execute("PRAGMA quick_check").fetchone()[0]
        if quick!="ok":
            return {"quick_check":str(quick)[:120],"healthy":False}
        tables={row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing=sorted({"memory_events","audit_events"}-tables)
        if missing:
            return {"quick_check":"ok","healthy":False,"missing_tables":missing}
        public=conn.execute(
            "SELECT COUNT(*) FROM memory_events WHERE room_id=? "
            "AND classification_level=? AND status=?",
            ("research-room","public","active")).fetchone()[0]
        audit=conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        return {"quick_check":"ok","healthy":True,
                "active_public_research_events":public,
                "audit_event_count":audit}


def diagnose(*,expected_main_db=None,opener=None,now=None):
    db_expected=Path(expected_main_db) if expected_main_db else (
        Path.home()/"klone"/"data"/"klone_mission_control.db")
    if not db_expected.is_absolute():
        raise ValueError("expected database path must be absolute")
    timestamp=now or datetime.now(timezone.utc).isoformat()
    result={}
    raw={}
    problems=[]
    for name,url in SERVICES:
        try:
            data=_read_health(url,opener=opener)
            if data.get("status")!="ok":
                raise ValueError("service did not return status=ok")
            if name=="main":
                if data.get("app")!="Klone":
                    raise ValueError("unexpected application at port 8000")
            elif name=="research":
                if data.get("service")!="klone-main-research-readonly" or (
                    data.get("read_only") is not True):
                    raise ValueError("8041 is not the KLONE read-only research service")
            raw[name]=data
            result[name]={"ok":True,"version":data.get("feature_version") or
                                               data.get("app_version") or "unreported"}
        except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,
                HTTPError,URLError,json.JSONDecodeError) as exc:
            result[name]={"ok":False,"error":str(exc)[:250]}
            problems.append(f"service_{name}_unavailable_or_invalid")
    db={"healthy":False,"status":"not_checked"}
    if "main" in raw:
        try:
            path=_validate_file(raw["main"].get("database_path"),db_expected)
            db=_inspect_db(path)
            db["status"]="checked"
            if not db["healthy"]:
                problems.append("main_database_integrity_or_schema_problem")
        except (OSError,TypeError,ValueError,sqlite3.Error) as exc:
            db={"healthy":False,"status":"validation_failed",
                "error":str(exc)[:250]}
            problems.append("main_database_integrity_or_schema_problem")
    if "research" in raw and "main" in raw:
        same=raw["research"].get("database_path")==raw["main"].get("database_path")
        result["research"]["main_db_matches"]=bool(same)
        if not same:
            problems.append("research_canary_database_mismatch")
    risk_codes=sorted(set(problems))
    return {
        "kind":"klone-e10-phone-doctor",
        "schema_version":1,
        "checked_at_utc":timestamp,
        "expected_main_db":str(db_expected),
        "services":result,"main_database":db,
        "health":"ok" if not risk_codes else "attention_required",
        "problems":risk_codes,
        "safety":{"writes_memory":False,"starts_services":False,
                  "fetches_external":False,"reads_private_rooms":False,
                  "modifies_permissions":False},
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E10 safe localhost/SQLite-only doctor")
    p.add_argument("--expected-main-db",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        report=diagnose(expected_main_db=args.expected_main_db)
        write_new_report(args.output.expanduser(),
                         json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (OSError,ValueError) as error:
        p.error(str(error))
    print(json.dumps({"kind":report["kind"],"health":report["health"],
                      "problems":report["problems"],
                      "memory_write":False},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
