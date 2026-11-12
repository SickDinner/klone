$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python tools/local_deploy.py doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path ".venv/Scripts/python.exe")) {
    python tools/local_deploy.py install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
python tools/local_deploy.py start @args
exit $LASTEXITCODE
