$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    docker compose exec -T api python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency check failed' }
    docker compose exec -T api python -m pytest -q -p no:cacheprovider -o 'addopts='
    if ($LASTEXITCODE -ne 0) { throw 'Backend regression failed' }
    docker compose exec -T frontend npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    Write-Host 'All project checks passed'
} finally {
    Pop-Location
}
