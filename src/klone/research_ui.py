from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
from urllib.parse import parse_qs

from .research_workflow import run_local_research
from .research_memory import ResearchMemory


def serve_research_ui(
    *, root: Path, database_path: Path, port: int = 8765,
) -> None:
    """Developer-only loopback UI for explicitly selected public text files.

    Never bind to a non-loopback address or expose this server on a network.
    """
    token = secrets.token_urlsafe(32)
    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535")
    allowed_root = root.resolve(strict=True)
    if not allowed_root.is_dir() or allowed_root.is_symlink():
        raise ValueError("Root must be a real directory")

    class Handler(BaseHTTPRequestHandler):
        def _trusted_request(self) -> bool:
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if host not in allowed:
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {
                f"http://127.0.0.1:{port}", f"http://localhost:{port}"
            }:
                return False
            if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
                return False
            return True

        def _send(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def _page(self, content: str = "") -> str:
            return ("""<!doctype html><html lang="fi"><meta charset="utf-8">
<title>KLONE Research Preview</title>
<style>body{font:16px system-ui;max-width:760px;margin:4rem auto;padding:1rem}
textarea,input{display:block;width:100%;margin:.6rem 0;padding:.5rem}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eee;padding:1rem}
button{padding:.6rem 1rem}</style><h1>KLONE Research Preview</h1>
<p>Paikallinen kokeilu. Vain julkinen .txt/.md-aineisto.</p>"""
                + f'<form method="post" action="/research">'
                + f'<input type="hidden" name="token" value="{html.escape(token, quote=True)}">'
                + '<label>Tiedosto (suhteellinen polku)<input name="file" required></label>'
                + '<label>Tutkimuskysymys<textarea name="question" required maxlength="500"></textarea></label>'
                + '<button type="submit">Tutki</button></form><p><a href="/history">Raporttihistoria</a></p>' + content + "</html>")

        def do_GET(self) -> None:
            if not self._trusted_request():
                self._send(403, "Forbidden")
                return
            if self.path == "/history":
                try:
                    reports = ResearchMemory(database_path).list_reports(limit=25)
                    rows = "".join(
                        "<li><strong>" + html.escape(item.title) +
                        "</strong> | versio " + str(item.version) +
                        " | " + html.escape(item.created_at) +
                        "<pre>" + html.escape(item.markdown) + "</pre></li>"
                        for item in reports
                    )
                    self._send(200, self._page("<h2>Tallennetut raportit</h2><ol>" + rows + "</ol>"))
                except Exception:
                    self._send(500, self._page("<p>Historiaa ei voitu lukea.</p>"))
                return
            if self.path != "/":
                self._send(404, "Not found")
                return
            self._send(200, self._page())

        def do_POST(self) -> None:
            if not self._trusted_request():
                self._send(403, "Forbidden")
                return
            if self.path != "/research":
                self._send(404, "Not found")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 4096:
                    self._send(413, "Request too large")
                    return
                fields = parse_qs(self.rfile.read(size).decode("utf-8"), strict_parsing=True)
                if (fields.get("token") != [token] or
                    len(fields.get("file", [])) != 1 or
                    len(fields.get("question", [])) != 1):
                    self._send(403, "Forbidden")
                    return
                outcome = run_local_research(
                    root=allowed_root, relative_paths=[fields["file"][0]],
                    question=fields["question"][0], room_id="public-room",
                    actor_role="owner", trace_id=secrets.token_hex(16),
                    classification_level="public", database_path=database_path,
                    persist_report=True,
                )
                self._send(200, self._page("<h2>Raportti</h2><pre>" +
                    html.escape(outcome.report.markdown) + "</pre>"))
            except Exception:
                self._send(400, self._page("<p>Tutkimus epäonnistui. Tarkista tiedosto ja kysymys.</p>"))

        def log_message(self, format: str, *args: object) -> None:
            return

    # Serialize requests: SQLite writes and local file reads are not concurrent.
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"KLONE local research UI: http://127.0.0.1:{server.server_port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE local research browser preview")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    serve_research_ui(root=args.root, database_path=args.database, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
