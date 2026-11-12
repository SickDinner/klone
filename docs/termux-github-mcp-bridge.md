# KLONE: GitHub ↔ Termux ↔ MCP (experimental)

The bridge uses a **polling Termux agent** and **GitHub Issues** as a task queue.
No inbound port, reverse shell, or SSH exposure is needed. The separate MCP
interface is a **local stdio MCP server**, not a ChatGPT plugin installation.
ChatGPT can use the already-connected GitHub integration to create and read
issues. Direct MCP use requires a compatible MCP host or an explicitly deployed,
authenticated remote MCP endpoint.

## One-time Termux setup

Use the existing checkout at `~/klone-next`. Run in Termux:

```sh
pkg update
pkg install -y python git
cd ~/klone-next
git fetch origin
git pull --ff-only origin main
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
mkdir -p ~/.config/klone
chmod 700 ~/.config/klone
```

Create `~/.config/klone/bridge.env` with these lines, substituting your
GitHub username and fine-grained GitHub token:

```sh
export KLONE_GITHUB_REPO='SickDinner/klone'
export KLONE_TRUSTED_ACTOR='YOUR_GITHUB_LOGIN'
export KLONE_GITHUB_TOKEN='YOUR_FINE_GRAINED_TOKEN'
export KLONE_ROOT="$HOME/klone-next"
```

The token should have **Issues read/write only** on this repository.
Do not put it in a chat, issue, commit, or public log. Secure the file:

```sh
chmod 600 ~/.config/klone/bridge.env
. ~/.config/klone/bridge.env
.venv/bin/python tools/termux_bridge.py once
```

To poll for tasks continuously while Termux remains running:

```sh
cd ~/klone-next
. ~/.config/klone/bridge.env
termux-wake-lock
.venv/bin/python tools/termux_bridge.py watch
```

Android may stop background processes; this is not a guaranteed always-on
service. Stop with Ctrl+C, then `termux-wake-unlock`.

## Task format

Create an **open GitHub Issue** with the label `klone-termux-task`,
authored by the account in `KLONE_TRUSTED_ACTOR`, with a body containing
exactly one JSON object:

```json
{"action":"tests"}
```

Supported actions: `status`, `git_status`, `tests`, `health`.
The agent comments with the exit code and truncated output. It marks a task
as processed *before* execution to avoid automatic replay; if GitHub comment
submission fails, the local state records it and a manual recovery is needed.
Issue authorship is checked, but **issue bodies can be edited**; do not grant
untrusted users edit rights to the trusted account's issues. Actions are
fixed and do not accept command arguments.

## Optional local MCP server

```sh
cd ~/klone-next
.venv/bin/python -m pip install 'mcp<2'
. ~/.config/klone/bridge.env
.venv/bin/python tools/klone_mcp.py
```

Configure a compatible MCP client to launch that command over stdio.
The server offers `bridge_capabilities`, `queue_termux_action`, and
`read_termux_task`. It does **not** expose arbitrary command execution.
For ChatGPT remote connectivity, a separate HTTPS-hosted, authenticated MCP
deployment is required; do not expose this stdio process or Termux directly
to the internet. This experimental implementation does not include that
deployment.

## Security boundaries

- Allowlisted read/diagnostic actions only; tests can still execute repository
  test code, so only run trusted repository revisions.
- No automatic code checkout or unreviewed remote script execution.
- Output is posted to a GitHub issue: use a **private repository** if logs
  might include sensitive paths or information. Review what tests print.
- Local token never belongs in GitHub issue text.
- No unattended destructive actions, root privileges, or LAN listener.

## Termux MCP compatibility (Android Python 3.13)

The bridge MCP module currently uses the MCP SDK **1.x** FastMCP API.
The SDK 2.x intentionally removed this import, so use `mcp<2` until
`tools/klone_mcp.py` is migrated and tested against 2.x.

On Termux, use its native `cryptography` package to avoid incompatible
pip-built Rust extension wheels:

```sh
pkg install -y python-cryptography
cd ~/klone-next
python -m venv --system-site-packages .venv-mcp
.venv-mcp/bin/python -m pip install 'mcp<2'
.venv-mcp/bin/python -c 'from cryptography.exceptions import InvalidTag; print("Crypto OK")'
.venv-mcp/bin/python -c 'from mcp.server.fastmcp import FastMCP; print("MCP OK")'
```

If the Python environment already has a broken pip-built cryptography,
remove it from that environment first. Do not uninstall the Termux
system package. Keep `.venv-mcp` separate from the KLONE application venv.
