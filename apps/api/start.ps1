$ErrorActionPreference = "Stop"

$apiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $apiRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment not found. Run: python -m venv .venv"
}

Push-Location $apiRoot
try {
    # Use one stable process. --reload creates a watcher and a child server;
    # repeated starts can leave multiple listeners on port 8000 and route
    # requests to an older process.
    & $python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
