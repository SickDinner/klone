"""KLONE v3.3 LAB: optional, localhost-only read-only Mission Control page.

The page displays only fixed v3.2 local health observations. No auth, remote
access, persistence, process management, background task or authority grant.
It deliberately does NOT probe its own port (8011) while handling a request.
"""
from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
from collections.abc import Callable, Mapping, Sequence

from .mission_control_live_v32 import (_validate_live_report,
                                       collect_local_service_observations)

_PORT = 8011
_DEFAULT_TIMEOUT_MS = 750
# Intentionally excludes this viewer's own port: avoid circular self-probes.
_PROBES = ("main-api", "next-api", "control-status", "chat-ui", "recovery-status")
_LABELS = {
    "main-api": "KLONE Main API",
    "next-api": "KLONE Next API",
    "control-status": "Control Status",
    "chat-ui": "Chat UI",
    "recovery-status": "Recovery Status",
}
_OBSERVATION_LABEL = {
    "reported_ok_unattested": "API ilmoittaa OK (ei varmennettu)",
    "reachable_unverified": "UI vastaa (toiminta varmentamatta)",
    "unverified": "Vastaus ei kelpaa terveystarkistukseen",
    "unavailable": "Ei tavoitettavissa",
}
_CSS = """
:root{color-scheme:dark}body{font:16px/1.5 system-ui,sans-serif;background:#101621;
color:#e8edf4;max-width:920px;margin:auto;padding:1.25rem}
header,section{padding:1rem;margin:1rem 0;border:1px solid #354252;border-radius:12px}
a{color:#b6d6ff}table{width:100%;border-collapse:collapse}th,td{text-align:left;
vertical-align:top;padding:.7rem;border-bottom:1px solid #354252}
small,.muted{color:#b4c0d0}.ok{color:#b8edc2}.warn{color:#ffcf89}
code{overflow-wrap:anywhere}h1,h2{line-height:1.2}
"""


def render_dashboard(snapshot: Mapping) -> bytes:
    """Validate and render an unauthenticated v3.2 report; no raw bodies."""
    if type(snapshot) is not dict:
        raise ValueError("invalid_dashboard_snapshot")
    _validate_live_report(snapshot)
    actual = {item["service_id"] for item in snapshot["services"]}
    if actual != set(_PROBES) or snapshot["probed_count"] != len(_PROBES):
        raise ValueError("incomplete_dashboard_probe_set")
    items = sorted(snapshot["services"], key=lambda x: (x["port"], x["service_id"]))
    cells = []
    for r in items:
        state = r["observation"]
        color = "ok" if state in ("reported_ok_unattested", "reachable_unverified") else "warn"
        cells.append(
            "<tr><td>" + escape(_LABELS[r["service_id"]]) + "</td>"
            + "<td><code>127.0.0.1:" + str(r["port"]) + "</code></td>"
            + "<td class='" + color + "'>" + escape(_OBSERVATION_LABEL[state]) + "</td>"
            + "<td>" + str(r["elapsed_ms"]) + " ms</td></tr>"
        )
    statuses = (f"{snapshot['reported_ok_count']} API:n ilmoittamaa OK-tilaa, "
                f"{snapshot['reachable_ui_count']} tavoitettavaa käyttöliittymää, "
                f"{snapshot['unavailable_count']} tavoittamatonta ja "
                f"{snapshot['unknown_count']} varmentamatonta vastausta")
    digest = escape(snapshot["report_sha256"])
    html = ("<!doctype html><html lang='fi'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>KLONE Mission Control – v3.3</title><style>" + _CSS + "</style></head>"
            "<body><header><h1>KLONE Mission Control</h1>"
            "<p>Paikallinen havaintonäkymä – v3.3 LAB</p>"
            "<p class='muted'>Ei pääsynvalvontaa; käyttö vain saman laitteen 127.0.0.1-osoitteessa. "
            "Ei agenttien suoritusta, käynnistämistä, tietokantakirjoituksia eikä tuotantohyväksyntää.</p>"
            "<p><a href='/'>Tarkista tilanne uudelleen</a></p></header>"
            "<section><h2>Paikalliset palvelut</h2><p>" + escape(statuses) + "</p>"
            "<table><thead><tr><th>Palvelu</th><th>Portti</th><th>Havainto</th><th>Viive</th>"
            "</tr></thead><tbody>" + "".join(cells) + "</tbody></table>"
            "<p class='muted'>Portti 8011: tämä sivu. Ei mukana kyselyissä, "
            "jotta palvelin ei kyselisi itseään.</p></section>"
            "<section><h2>Todistettavuus</h2><p>Paikallisen havainnon SHA-256: "
            "<code>" + digest + "</code></p>"
            "<p class='muted'>Tiiviste todistaa vain esitetyn raportin muuttumattomuuden "
            "siitä hetkestä, kun se laskettiin. Palvelimen identiteettiä, lähteen aitoutta "
            "tai tietokannan eheyttä ei ole ulkoisesti varmennettu.</p>"
            "<p>Testien tila: ei kysytty tältä sivulta. "
            "V3.2:n erillinen Android-testi on raportoitava omana evidenssinään.</p>"
            "</section><footer><small>Vain luku · ei evästeitä · ei telemetrian lähettämistä "
            "ulkoverkkoon · ei taustapäivitystä</small></footer></body></html>")
    return html.encode("utf-8")


def make_handler(*, port: int = _PORT, timeout_ms: int = _DEFAULT_TIMEOUT_MS,
                 collector: Callable | None = None) -> type[BaseHTTPRequestHandler]:
    """Return a request handler with strict Host/Origin guards for the UI."""
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid_dashboard_port")
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 3000:
        raise ValueError("invalid_dashboard_timeout")
    if collector is not None and not callable(collector):
        raise ValueError("invalid_dashboard_collector")
    collect = collector or collect_local_service_observations
    host_ok = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origin_ok = {"http://" + x for x in host_ok}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # no request path/header leakage
            pass

        def do_GET(self):
            if (self.headers.get("Host") not in host_ok or
                    self.headers.get("Origin") not in (None, *origin_ok) or
                    self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site"):
                self.send_error(403)
                return
            if self.path != "/":
                self.send_error(404)
                return
            try:
                snapshot = collect(service_ids=_PROBES, timeout_ms=timeout_ms)
                payload = render_dashboard(snapshot)
                code = 200
            except Exception:
                # No untrusted traceback/data in the HTTP response.
                payload = b"Mission Control: paikallinen havainto ei ole saatavilla"
                code = 503
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8" if code == 200 else "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def serve_dashboard() -> int:
    """Explicit foreground opt-in only. Never touch the working port 8000."""
    try:
        with HTTPServer(("127.0.0.1", _PORT), make_handler()) as server:
            print("KLONE v3.3 Mission Control: http://127.0.0.1:8011/", flush=True)
            print("Paikallinen esikatselu. Ctrl+C pysayttaa.", flush=True)
            try:
                server.serve_forever(poll_interval=0.25)
            except KeyboardInterrupt:
                return 0
    except OSError:
        print("Mission Control -portti 8011 varattu tai ei kaytettavissa.", flush=True)
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE v3.3 local-only read-only Mission Control preview")
    parser.add_argument("--serve-local", action="store_true", help="explicitly start 127.0.0.1:8011 page")
    args = parser.parse_args(argv)
    if not args.serve_local:
        parser.error("--serve-local vaaditaan; ohjelma ei käynnisty automaattisesti")
    return serve_dashboard()


if __name__ == "__main__":
    raise SystemExit(main())
