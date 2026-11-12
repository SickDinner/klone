# KLONE local deployment: Windows 11 + Android Termux

Both platforms run their **own** local KLONE instance and SQLite data. This
does **not** implement synchronization, replication, shared secrets or a remote
control channel. There is no implicit data sharing between devices.

## Windows 11 (PowerShell)

Install Python 3.11 or 3.12 and Git. Clone the reviewed branch:

```powershell
git clone --branch feat/security-s1-deny-default-core https://github.com/SickDinner/klone.git
cd klone
python tools/local_deploy.py doctor
python tools/local_deploy.py install
python tools/local_deploy.py start
```

Alternatively run `powershell -File tools/start-windows.ps1`.
Open http://127.0.0.1:8000/ on **that same PC**.

## Android Termux

Use Termux from a maintained distribution, install Python and Git, then:

```sh
pkg update
pkg install python git
git clone --branch feat/security-s1-deny-default-core https://github.com/SickDinner/klone.git
cd klone
python tools/local_deploy.py doctor
python tools/local_deploy.py install
python tools/local_deploy.py start
```

Alternatively run `bash tools/start-termux.sh`.
Open http://127.0.0.1:8000/ in the **same phone** browser.

**Android compatibility caveat:** `pip install -e .` may fail to build
dependencies such as Pillow or Pydantic on some Termux/Python versions. This
launcher intentionally reports that failure rather than bypassing dependencies.
Resolve from package-specific Termux build guidance before proceeding.

## Operational safeguards

- The server binds to `127.0.0.1` only, never `0.0.0.0`.
- `--port 8001` can be supplied if port 8000 is occupied.
- Stop using Ctrl+C. No service is installed or started on boot.
- Do not run `--reload` for normal operation.
- Do not copy live SQLite database files between devices.
- Do not expose the development server with port forwarding, tunnels or public
  reverse proxies. No production identity gateway is installed.
- Keep sensitive genomic exports and authentication secrets outside Git.
- Approval and audit modules remain experimental. Constitution writes and
  sensitive external egress are not activated by this deployment.
- Before upgrading, stop the app, back up local data, inspect migration notes,
  then update the checked-out branch and reinstall.
- Run `python -m unittest discover -s tests` from the activated environment
  for regression checks. On Windows, use `.venv\\Scripts\\python.exe`;
  on Termux, `.venv/bin/python`.

## Acceptance criteria

1. Doctor passes and virtualenv installation succeeds.
2. The UI responds on the local loopback URL on each device.
3. Regression tests pass on each actual device.
4. A second start on the same port fails clearly.
5. No remote interface is bound, and no cross-device sync is assumed.
6. Local user data remains isolated on each device.
