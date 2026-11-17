"""Developer-only, loopback-only read-only Mission Control status page.

Not an authenticated multi-user server. Do not expose beyond localhost.
The recovery inspector uses SQLite mode=ro and does not mutate the DB.
"""
from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .research_recovery_inspection import inspect_research_recovery
from .research_audit_consistency import inspect_audit_consistency


def render_research_status(*, database_path: Path) -> str:
    status = inspect_research_recovery(database_path=database_path)
    integrity = inspect_audit_consistency(database_path=database_path)

    def section(title: str, values: tuple[str, ...]) -> str:
        items = "".join("<li>" + html.escape(value, quote=True) + "</li>"
                        for value in values)
        return ("<section><h2>" + html.escape(title) + " (" +
                str(len(values)) + ")</h2><ul>" +
                (items or "<li>Ei merkintöjä</li>") + "</ul></section>")

    return ("""<!doctype html><html lang="fi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KLONE Mission Control</title><style>
body{font:16px system-ui;background:#101821;color:#edf4fc;max-width:820px;
margin:2rem auto;padding:1rem}section{background:#1c2937;border-radius:12px;
padding:1rem;margin:1rem 0}li{overflow-wrap:anywhere;margin:.4rem 0}
small{color:#aebccc}</style></head><body><h1>KLONE Mission Control</h1>
<p>Julkisen tutkimusjärjestelmän tilannekuva</p>
<small>Vain luku. Ei automaattista palautusta tai tutkimuksen julkaisua.</small>"""
            + section("Kesken jääneet tutkimusajot",
                      status.started_without_terminal)
            + section("Valmistuneet ilman auditointijonoa",
                      status.completed_without_outbox)
            + section("Auditointitoimitusta odottavat",
                      status.pending_audit_delivery)
            + "<h2>Tietokannan eheys: " +
              ("OK" if integrity.healthy else "TARKISTETTAVA") + "</h2>"
            + section("Valmistuneet ilman tallennettua versiota",
                      integrity.completed_missing_snapshot)
            + section("Auditointitapahtumat ilman valmistunutta ajoa",
                      integrity.outbox_missing_completed)
            + section("Auditointitapahtumien versioristiriidat",
                      integrity.outbox_version_mismatch)
            + section("Virheelliset tapahtumatunnukset",
                      integrity.malformed_event_ids)
            + "</body></html>")


def serve_research_status(*, database_path: Path, port: int = 8767) -> None:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid port")
    # Reject missing or invalid schema before starting the server.
    inspect_research_recovery(database_path=database_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if (self.path != "/" or
                    self.headers.get("Host") not in
                    {f"127.0.0.1:{port}", f"localhost:{port}"} or
                    self.headers.get("Origin") not in
                    {None, f"http://127.0.0.1:{port}",
                     f"http://localhost:{port}"} or
                    self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site"):
                self.send_error(403)
                return
            try:
                data = render_research_status(database_path=database_path).encode("utf-8")
                code = 200
            except Exception:
                data = b"Research status unavailable"
                code = 503
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="KLONE local status page")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    serve_research_status(database_path=args.database, port=args.port)


if __name__ == "__main__":
    main()
