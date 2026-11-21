#!/usr/bin/env python3
"""KLONE Reality Ledger: read-only checkout and optional localhost inventory.

Source files, test files, executed tests, live services and approved deployment
are distinct evidence classes. This tool does not execute tests or change KLONE.
"""
from __future__ import annotations

import argparse
import ast
import html
import http.client
import json
import os
from pathlib import Path
import subprocess
import tomllib

# Check paths, never infer capability readiness from names alone.
# The same inventory can evaluate main and a feature worktree independently.
CAPABILITIES = (
    ("core", "Core / Mission Control", ("src/klone/main.py", "src/klone/api.py"), ("tests/test_bedrock_b00_1.py",)),
    ("hypervisor", "Hypervisor / policy", ("src/klone/hypervisor_runtime.py", "src/klone/guards.py"), ("tests/test_hypervisor_runtime_contract.py",)),
    ("memory", "Memory Core / provenance", ("src/klone/memory.py", "src/klone/repository.py"), ("tests/test_memory_phase_2b3.py", "tests/test_memory_phase_2c4.py")),
    ("dialogue", "Dialogue Corpus / Clone Chat", ("src/klone/dialogue.py",), ("tests/test_phase_2b_8.py",)),
    ("ingest", "Media Lake / ingest", ("src/klone/ingest.py", "src/klone/ingest_fingerprint.py"), ("tests/test_phase_g1_5.py",)),
    ("art", "Art Lab", ("src/klone/art.py",), ("tests/test_phase_v1_3.py",)),
    ("genomics", "Genomics (public research)", ("src/klone/genomics_public.py", "src/klone/genomics_variants.py"), ("tests/test_genomics_public.py", "tests/test_genomics_variants.py")),
    ("cognition", "Cognition / neuromodulators", ("src/klone/cognition_neurocortex.py", "src/klone/cognition_learning.py"), ("tests/test_cognition_neurocortex.py",)),
    ("council72", "Council72 deterministic engine", ("src/klone/council72.py", "src/klone/council72_session.py"), ("tests/test_council72.py", "tests/test_council72_session.py")),
    ("evidence", "Evidence Forensics", ("src/klone/evidence_forensics.py", "src/klone/evidence_artifact_inspector.py"), ("tests/test_evidence_forensics.py",)),
    ("research", "Research workflow", ("src/klone/integrated_research_core.py",), ("tests/test_integrated_research_core.py",)),
    ("world", "World Memory / simulations", ("src/klone/simulation.py",), ("tests/test_phase_w1_4.py",)),
    ("security", "Egress / approval policy", ("src/klone/egress_policy.py", "src/klone/approval_policy.py"), ("tests/test_security_foundation_policy.py",)),
    ("limbo", "Limbo Atlas research", ("src/klone/limbo_atlas.py",), ("tests/test_limbo_atlas.py",)),
    ("council_llm", "Council72 LLM bridge", ("src/klone/council72_intelligence_bridge.py",), ("tests/test_council72_intelligence_bridge.py",)),
    ("council_quality", "Council72 quality / debate", ("src/klone/council72_quality_lab.py", "src/klone/council72_debate.py"), ("tests/test_council72_quality_debate.py",)),
    ("knowledge_atlas", "Knowledge Atlas / Wikipedia", ("src/klone/knowledge_atlas.py",), ("tests/test_knowledge_atlas.py",)),
    ("noki", "Noki companion", ("src/klone/static/noki.html",), ("tests/test_noki_companion.py",)),
)

# Only these exact loopback endpoints may be probed, and only on explicit opt-in.
LOOPBACK_ENDPOINTS = ((8000, "/api/health"), (8031, "/api/health"), (8041, "/health"))
POTENTIAL_REPO_ARTIFACTS = ("tmp_smoke.sqlite", "chat_server.err.log", "chat_server.out.log")
MAX_METADATA = 1_048_576


def _safe_file(root: Path, relative: str) -> Path | None:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if not path.resolve().is_relative_to(root):
            return None
        if path.stat().st_size > MAX_METADATA:
            return None
    except OSError:
        return None
    return path


def _git(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True, text=True, timeout=4, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _versions(root: Path) -> dict[str, str | None]:
    package = None
    runtime = None
    file = _safe_file(root, "pyproject.toml")
    if file:
        try:
            package = tomllib.loads(file.read_text(encoding="utf-8")).get("project", {}).get("version")
        except (ValueError, OSError, UnicodeError):
            pass
    file = _safe_file(root, "src/klone/contracts.py")
    if file:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    if any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets):
                        runtime = node.value.value if isinstance(node.value.value, str) else None
                        break
        except (SyntaxError, ValueError, OSError, UnicodeError):
            pass
    return {"package": package if isinstance(package, str) else None,
            "runtime": runtime}


def _probe(port: int, route: str) -> dict:
    if (port, route) not in LOOPBACK_ENDPOINTS:
        raise ValueError("Only fixed KLONE loopback endpoints are permitted")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
    try:
        connection.request("GET", route, headers={"Accept": "application/json"})
        response = connection.getresponse()
        content = response.read(8193)
        if len(content) > 8192:
            return {"state": "invalid_response", "http_status": response.status}
        if response.status != 200:
            return {"state": "unhealthy", "http_status": response.status}
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            return {"state": "invalid_response", "http_status": response.status}
        if not isinstance(payload, dict):
            return {"state": "invalid_response", "http_status": response.status}
        good = payload.get("status") == "ok" or payload.get("health") == "ok"
        # Never expose database paths, keys, diagnostic bodies or personal data.
        return {"state": "health_reported_ok" if good else "unhealthy",
                "http_status": response.status,
                "app_version": payload.get("app_version") if
                isinstance(payload.get("app_version"), str) else None}
    except (OSError, http.client.HTTPException):
        return {"state": "unreachable"}
    finally:
        connection.close()


def inventory(root: Path, *, probe_local: bool = False) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Checkout root must be an existing directory")
    head = _git(root, "rev-parse", "--verify", "HEAD")
    branch = _git(root, "branch", "--show-current") if head else None
    dirty = _git(root, "status", "--porcelain", "--untracked-files=normal") if head else None
    versions = _versions(root)
    capabilities = []
    for key, label, sources, tests in CAPABILITIES:
        existing_sources = [path for path in sources if _safe_file(root, path)]
        existing_tests = [path for path in tests if _safe_file(root, path)]
        source_state = ("present" if len(existing_sources) == len(sources) else
                        "partial" if existing_sources else "not_in_checkout")
        test_state = ("files_present" if len(existing_tests) == len(tests) else
                      "files_partial" if existing_tests else "not_in_checkout")
        capabilities.append({
            "id": key, "name": label, "source_state": source_state,
            "source_present": existing_sources,
            "source_missing": sorted(set(sources) - set(existing_sources)),
            "test_state": test_state, "test_present": existing_tests,
            "test_missing": sorted(set(tests) - set(existing_tests)),
            "execution_state": "not_executed_by_reality_ledger",
            "runtime_state": "not_verified_by_file_inventory",
        })

    flags = []
    if versions["package"] and versions["runtime"] and versions["package"] != versions["runtime"]:
        flags.append("package_version_differs_from_app_version")
    tracked = []
    for name in POTENTIAL_REPO_ARTIFACTS:
        if _safe_file(root, name) and _git(root, "ls-files", "--error-unmatch", "--", name) is not None:
            tracked.append(name)
    if tracked:
        flags.append("tracked_runtime_artifacts_require_content_review")
    chat = _safe_file(root, "src/klone/dialogue.py")
    if chat and "External model rendering is disabled" in chat.read_text(encoding="utf-8", errors="replace"):
        flags.append("clone_chat_external_rendering_disabled_in_source")

    services = ([
        {"port": port, "route": route, **_probe(port, route)}
        for port, route in LOOPBACK_ENDPOINTS
    ] if probe_local else [
        {"port": port, "route": route, "state": "not_probed"}
        for port, route in LOOPBACK_ENDPOINTS
    ])
    return {
        "schema": "klone.reality_ledger.v1",
        "checkout": {"head": head, "branch": branch,
                     "working_tree_clean": None if dirty is None else dirty == ""},
        "versions": versions,
        "capabilities": capabilities,
        "local_services": services,
        "repository_artifacts_to_review": tracked,
        "flags": flags,
        "tests_executed": False,
        "deployment_approved": False,
        "limitations": [
            "A source file or test file does not prove behavior or test success.",
            "Loopback HTTP health does not prove readiness, identity or security.",
            "Feature branches must be inventoried separately; absent does not mean unimplemented elsewhere.",
            "This tool performs no deployments, database reads, model calls or tests.",
        ],
    }


def as_html(report: dict) -> str:
    e = lambda value: html.escape(str(value), quote=True)
    rows = []
    for cap in report["capabilities"]:
        rows.append("<tr><td>" + e(cap["name"]) + "</td><td>" +
                    e(cap["source_state"]) + "</td><td>" +
                    e(cap["test_state"]) + "</td></tr>")
    services = "".join("<li>127.0.0.1:" + e(item["port"]) +
                       e(item["route"]) + " — " + e(item["state"]) +
                       "</li>" for item in report["local_services"])
    flags = "".join("<li>" + e(value) + "</li>" for value in report["flags"])
    return (
        "<!doctype html><html lang='fi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>KLONE – todellisuuskartta</title><style>"
        "body{font:16px system-ui;max-width:900px;margin:auto;padding:1.4rem;"
        "color:#e9ecf1;background:#10151b}table{border-collapse:collapse;width:100%}"
        "th,td{text-align:left;border-bottom:1px solid #43505d;padding:.65rem}"
        "th{color:#bcd4e2}small{color:#abb8c2}li{margin:.4rem 0}"
        "</style></head><body><h1>KLONE – todellisuuskartta</h1>"
        "<p>Haara: " + e(report["checkout"]["branch"]) + " · Commit: " +
        e(report["checkout"]["head"]) + "</p><p><strong>Ei testiajotodistus "
        "eikä käyttöönottohyväksyntä.</strong></p>"
        "<h2>Osa-alueet</h2><table><thead><tr><th>Osa</th><th>Lähdekoodi</th>"
        "<th>Testitiedostot</th></tr></thead><tbody>" + "".join(rows) +
        "</tbody></table><h2>Paikalliset palvelut</h2><ul>" + services +
        "</ul><h2>Selvitettävät havainnot</h2><ul>" + flags +
        "</ul><small>Vain paikallinen, ei verkkolatauksia tai automaattisia "
        "korjauksia. Ominaisuuksien olemassaolo ei todista toimivuutta.</small>"
        "</body></html>"
    )


def _write_new(root: Path, destination: Path, content: str) -> None:
    destination = destination.expanduser()
    resolved = destination.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("Report output must be outside the checkout")
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONEn paikallinen todellisuuskartta")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--probe-local", action="store_true",
                        help="Tarkista vain ennalta määrätyt 127.0.0.1-palvelut")
    parser.add_argument("--format", choices=("json", "html"), default="json")
    parser.add_argument("--output", type=Path, help="Luo uusi raportti repositorion ulkopuolelle")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    report = inventory(root, probe_local=args.probe_local)
    content = (as_html(report) if args.format == "html" else
               json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.output:
        _write_new(root, args.output, content + "\n")
        print("Luotu uusi paikallinen raportti:", args.output)
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
