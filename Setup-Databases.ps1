# ==============================================================================
# Script: Setup-Databases.ps1
# Purpose: Initialize UAT and Production SQLite audit databases, verify schema,
#          and ensure .env is configured to route mock testing to UAT.
# ==============================================================================

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   FIRST ASSURANCE - ACCOUNT UNLOCK DATABASE SETUP (UAT & PROD)      " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = Get-Location
}

$DataDir = Join-Path $WorkspaceRoot "data"
if (-not (Test-Path $DataDir)) {
    Write-Host "[*] Creating data directory: $DataDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

$UatDb = Join-Path $DataDir "audit_log_uat.db"
$ProdDb = Join-Path $DataDir "audit_log_prod.db"
$EnvFile = Join-Path $WorkspaceRoot ".env"

# 1. Initialize UAT Database
Write-Host "`n[1/3] Initializing UAT Database ($UatDb)..." -ForegroundColor Yellow
$InitUatCmd = "from backend.database.audit_db import init_db, get_db_path; init_db(get_db_path('UAT'))"
python -c $InitUatCmd
if ($LASTEXITCODE -eq 0 -and (Test-Path $UatDb)) {
    Write-Host " [OK] UAT Database initialized successfully: audit_log_uat.db" -ForegroundColor Green
} else {
    Write-Host " [X] Failed to initialize UAT database." -ForegroundColor Red
}

# 2. Initialize Production Database
Write-Host "`n[2/3] Initializing Production Database ($ProdDb)..." -ForegroundColor Yellow
$InitProdCmd = "from backend.database.audit_db import init_db, get_db_path; init_db(get_db_path('PRODUCTION'))"
python -c $InitProdCmd
if ($LASTEXITCODE -eq 0 -and (Test-Path $ProdDb)) {
    Write-Host " [OK] Production Database initialized successfully: audit_log_prod.db" -ForegroundColor Green
} else {
    Write-Host " [X] Failed to initialize Production database." -ForegroundColor Red
}

# 3. Configure .env for UAT Routing
Write-Host "`n[3/3] Checking .env configuration..." -ForegroundColor Yellow
if (Test-Path $EnvFile) {
    $content = Get-Content $EnvFile -Raw
    
    # Ensure ENVIRONMENT=UAT
    if ($content -match "ENVIRONMENT\s*=") {
        $content = $content -replace "ENVIRONMENT\s*=\s*\w+", "ENVIRONMENT=UAT"
    } else {
        $content = "ENVIRONMENT=UAT`r`n" + $content
    }

    # Ensure DATA_SOURCE=mock
    if ($content -match "DATA_SOURCE\s*=") {
        $content = $content -replace "DATA_SOURCE\s*=\s*\w+", "DATA_SOURCE=mock"
    } else {
        $content = "DATA_SOURCE=mock`r`n" + $content
    }

    Set-Content -Path $EnvFile -Value $content -Encoding utf8
    Write-Host " [OK] Verified .env: ENVIRONMENT=UAT, DATA_SOURCE=mock" -ForegroundColor Green
} else {
    Write-Host " [!] .env file not found, creating from defaults..." -ForegroundColor Yellow
    $defaultEnv = "ENVIRONMENT=UAT`r`nDATA_SOURCE=mock`r`nPORT=3978`r`n"
    Set-Content -Path $EnvFile -Value $defaultEnv -Encoding utf8
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                        SETUP COMPLETE                                 " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " - UAT Database:        $UatDb" -ForegroundColor White
Write-Host " - Production Database: $ProdDb" -ForegroundColor White
Write-Host " - Active Routing:      UAT (All mock tests will write to audit_log_uat.db)" -ForegroundColor White
Write-Host ""
Write-Host "Next steps to view logs:" -ForegroundColor Yellow
Write-Host "  1. Run in PowerShell: python view_audit_logs.py uat" -ForegroundColor Gray
Write-Host "  2. Or run: .\Watch-AuditLogs.ps1" -ForegroundColor Gray
Write-Host "  3. In VS Code: Open 'data/audit_log_uat.db' with SQLite Viewer extension." -ForegroundColor Gray
Write-Host "======================================================================" -ForegroundColor Cyan
