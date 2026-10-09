# ==============================================================================
# Script: Watch-AuditLogs.ps1
# Purpose: Real-time terminal watcher for incoming audit logs in UAT or PROD.
# Usage: .\Watch-AuditLogs.ps1 [-Environment UAT]
# ==============================================================================
param(
    [string]$Environment = "UAT",
    [int]$PollSeconds = 2
)

$WorkspaceRoot = $PSScriptRoot
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = Get-Location
}

$DbFileName = if ($Environment -match "PROD") { "audit_log_prod.db" } else { "audit_log_uat.db" }
$DbPath = Join-Path (Join-Path $WorkspaceRoot "data") $DbFileName

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "         REAL-TIME AUDIT LOG WATCHER - [$($Environment.ToUpper())]" -ForegroundColor Cyan
Write-Host " Database File: $DbPath" -ForegroundColor White
Write-Host " Polling interval: $PollSeconds second(s) | Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host "================================================================================" -ForegroundColor Cyan

if (-not (Test-Path $DbPath)) {
    Write-Host "[!] Database file does not exist yet. Run .\Setup-Databases.ps1 first." -ForegroundColor Red
    exit 1
}

$lastSeenId = 0

# Query initial max id
$initScript = "import sqlite3; conn = sqlite3.connect(r'$DbPath'); print(conn.cursor().execute('SELECT IFNULL(MAX(id), 0) FROM audit_logs').fetchone()[0]); conn.close()"
try {
    $lastSeenId = [int](python -c $initScript)
} catch {
    $lastSeenId = 0
}

Write-Host "Watching for new audit events after ID: $lastSeenId...`n" -ForegroundColor Yellow
$header = "{0,-4} | {1,-19} | {2,-16} | {3,-15} | {4,-24} | {5,-10} | {6}" -f "ID", "Timestamp", "Requester", "Target", "Action", "Status", "Details"
Write-Host $header -ForegroundColor Cyan
Write-Host ("-" * 110) -ForegroundColor DarkGray

while ($true) {
    $queryScript = @"
import sqlite3, json, sys
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'$DbPath')
conn.row_factory = sqlite3.Row
rows = conn.cursor().execute(
    'SELECT id, timestamp, action, requester_name, target_account_name, target_account_id, status, details FROM audit_logs WHERE id > ? ORDER BY id ASC',
    ($lastSeenId,)
).fetchall()
print(json.dumps([dict(r) for r in rows]))
conn.close()
"@

    $jsonOutput = python -c $queryScript
    if ($jsonOutput) {
        try {
            $records = $jsonOutput | ConvertFrom-Json
            foreach ($rec in $records) {
                $lastSeenId = [math]::Max($lastSeenId, $rec.id)
                $ts = if ($rec.timestamp) { $rec.timestamp.Substring(0, [math]::Min(19, $rec.timestamp.Length)) } else { "N/A" }
                $req = if ($rec.requester_name) { $rec.requester_name.Substring(0, [math]::Min(16, $rec.requester_name.Length)) } else { "Unknown" }
                $target = if ($rec.target_account_name) { $rec.target_account_name.Substring(0, [math]::Min(15, $rec.target_account_name.Length)) } else { "N/A" }
                $action = if ($rec.action) { $rec.action.Substring(0, [math]::Min(24, $rec.action.Length)) } else { "" }
                $status = if ($rec.status) { $rec.status.Substring(0, [math]::Min(10, $rec.status.Length)) } else { "" }
                $details = if ($rec.details) { $rec.details.Substring(0, [math]::Min(35, $rec.details.Length)) } else { "" }

                $color = "White"
                if ($status -eq "SUCCESS") { $color = "Green" }
                elseif ($status -in "FAILURE", "BLOCKED", "RATE_LIMITED") { $color = "Red" }
                elseif ($status -eq "CANCELLED") { $color = "Yellow" }

                $line = "{0,-4} | {1,-19} | {2,-16} | {3,-15} | {4,-24} | {5,-10} | {6}" -f $rec.id, $ts, $req, $target, $action, $status, $details
                Write-Host $line -ForegroundColor $color
            }
        } catch {
            # pass on parse error
        }
    }

    Start-Sleep -Seconds $PollSeconds
}
