$ErrorActionPreference = "Stop"

# Reuse the locally built application images as the base layer so day-to-day
# code rebuilds do not need to reach Docker Hub again.
$env:BACKEND_BASE_IMAGE = "agent-backend:latest"
$env:FRONTEND_BASE_IMAGE = "agent-frontend:latest"

docker compose build backend frontend --pull=false
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

docker compose up -d backend frontend
exit $LASTEXITCODE
