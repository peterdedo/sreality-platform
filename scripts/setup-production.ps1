# Sreality Platform — production wiring (Railway backend + Vercel proxy)
# Prerequisites: npx @railway/cli login, npx vercel login (already done for peterdedo)
#
# Usage from repo root:
#   .\scripts\setup-production.ps1
#   .\scripts\setup-production.ps1 -BackendUrl "https://your-app.up.railway.app"

param(
    [string]$BackendUrl = "",
    [string]$ApiKey = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not $ApiKey) {
    $ApiKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
}

Write-Host "=== Sreality production setup ===" -ForegroundColor Cyan
Write-Host ""

# --- Railway ---
Write-Host "1) Railway backend + Postgres" -ForegroundColor Yellow
Write-Host "   Run these if you have not deployed yet:"
Write-Host ""
Write-Host "   cd `"$RepoRoot`""
Write-Host "   npx @railway/cli login"
Write-Host "   npx @railway/cli init          # new project"
Write-Host "   npx @railway/cli add --database postgres"
Write-Host "   npx @railway/cli add --service   # link backend service to repo"
Write-Host ""
Write-Host "   In Railway dashboard for the BACKEND service:"
Write-Host "   - Root Directory = backend"
Write-Host "   - Variables:"
Write-Host "       APP_ENV=production"
Write-Host "       API_KEY=$ApiKey"
Write-Host "       CORS_ORIGINS=[`"https://sreality-platform.vercel.app`"]"
Write-Host "       ENABLE_SCHEDULER=true"
Write-Host "   - DATABASE_URL is auto-linked from Postgres plugin"
Write-Host "   - Networking -> Generate Domain"
Write-Host ""
Write-Host "   Deploy: npx @railway/cli up --service <backend-service>"
Write-Host ""

if (-not $BackendUrl) {
    $BackendUrl = Read-Host "Paste your Railway public URL (e.g. https://xxx.up.railway.app)"
}
$BackendUrl = $BackendUrl.TrimEnd("/")

Write-Host ""
Write-Host "2) Vercel env vars + redeploy" -ForegroundColor Yellow
Set-Location $RepoRoot

Write-Host "   Setting BACKEND_URL and VITE_API_KEY on Vercel (Production)..."
$BackendUrl | npx vercel env add BACKEND_URL production --scope peterdedos-projects --force 2>$null
if ($LASTEXITCODE -ne 0) {
    $BackendUrl | npx vercel env add BACKEND_URL production --scope peterdedos-projects
}
$ApiKey | npx vercel env add VITE_API_KEY production --scope peterdedos-projects --force 2>$null
if ($LASTEXITCODE -ne 0) {
    $ApiKey | npx vercel env add VITE_API_KEY production --scope peterdedos-projects
}

Write-Host "   Redeploying frontend..."
npx vercel deploy --prod --yes --scope peterdedos-projects

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Verify:"
Write-Host "  $BackendUrl/health"
Write-Host "  https://sreality-platform.vercel.app/health"
Write-Host "  https://sreality-platform.vercel.app/api/analytics/dataset-summary"
Write-Host ""
Write-Host "Backend API_KEY (save in Railway if not set yet): $ApiKey"
