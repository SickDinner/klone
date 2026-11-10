# KLONE Research Agent: local developer preview

This is a **local, public-data-only developer preview**, not an authenticated API,
a security sandbox, an autonomous researcher or a production deployment.

Run from an installed KLONE environment:

```bash
python -m klone.research_cli --root ./research_notes --file notes.md --question "DNA chronology" --database ./research-audit.sqlite --trace-id demo-001
```

The selected directory must already exist. Only explicitly named UTF-8
`.md` and `.txt` files are loaded. The output is an evidence-only Markdown
report printed to stdout, with trace-linked audit events in SQLite.

## Boundaries

- This CLI is restricted to `public-room` and `public` classification.
- The CLI uses the local `owner` role as a **developer convenience**, not proof
  of user identity. Never expose it through a network service.
- Only use a trusted local directory and a trusted database path.
- There is no automatic source credibility verification, LLM synthesis,
  web search, authentication, OS sandboxing or hardened filesystem isolation.
- Do not use this preview for private, medical or otherwise sensitive records.
- SQLite events track execution; the audit log is not tamper-proof.
- Each source reference includes a SHA-256 digest of its content.
- Run a single request at a time until concurrency and filesystem race
  handling have been hardened.

The goal is to validate the full source → policy → retrieval → report → audit
path before expanding the feature surface.

## 3B.1 local browser hardening

Start the browser UI using:

```bash
python -m klone.research_ui --root ./research_notes --database ./research-audit.sqlite --port 8765
```

Open `http://127.0.0.1:8765/` on the same machine. The server binds
only to IPv4 loopback, processes requests sequentially and rejects unexpected
Host/Origin and cross-site Fetch Metadata. The form has a random per-process
CSRF token. These checks are **not user authentication**. A process running
locally under the same account can still access the UI and files; use a
trusted account and directory. Do not forward or proxy the port.

The UI does not render source Markdown as HTML. No external scripts are loaded.

## Experimental report history (3B.3)

The local browser UI saves completed public-room reports in SQLite and shows
up to 25 recent report versions at `/history`. Reports are HTML-escaped and
SHA-256 checked on read. The developer CLI saves only with `--save-report`.
These records contain source excerpts; do not point the preview at sensitive
files. History is not authenticated, encrypted, or tamper-proof. No automatic
retention/deletion policy is implemented.
