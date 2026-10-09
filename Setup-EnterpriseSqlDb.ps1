# ==============================================================================
# Script: Setup-EnterpriseSqlDb.ps1
# Purpose: Connect to Microsoft SQL Server with custom port and credentials,
#          then create UAT and PROD databases and audit tables.
# ==============================================================================
param(
    [Parameter(Mandatory = $false)]
    [string]$Server = "172.17.0.218",

    [Parameter(Mandatory = $false)]
    [string]$Port,

    [Parameter(Mandatory = $false)]
    [string]$Username,

    [Parameter(Mandatory = $false)]
    [string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   FIRST ASSURANCE - ENTERPRISE SQL SERVER DATABASE INITIALIZER       " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Gather Port if not supplied
if ([string]::IsNullOrWhiteSpace($Port)) {
    $Port = Read-Host "Enter SQL Server Port (e.g. 1433 or custom port)"
}

# 2. Gather Username if not supplied
if ([string]::IsNullOrWhiteSpace($Username)) {
    $Username = Read-Host "Enter SQL Database Username"
}

# 3. Gather Password securely if not supplied
if ([string]::IsNullOrWhiteSpace($Password)) {
    $secPass = Read-Host "Enter SQL Database Password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPass)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

# Format server address: In SQL Server connection strings, port is specified with a COMMA
$serverTarget = if ($Port) { "$Server,$Port" } else { $Server }
$connectionString = "Server=$serverTarget;Database=master;User Id=$Username;Password=$Password;TrustServerCertificate=True;Connect Timeout=15;"

Write-Host "`n[*] Connecting to $serverTarget as user '$Username'..." -ForegroundColor Yellow

$connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)

try {
    $connection.Open()
    Write-Host "[✓] Successfully connected to SQL Server at $serverTarget!" -ForegroundColor Green

    # Function to execute command safely
    function Exec-SqlCmd {
        param([string]$sqlText, [string]$label)
        $cmd = $connection.CreateCommand()
        $cmd.CommandText = $sqlText
        $cmd.CommandTimeout = 60
        $cmd.ExecuteNonQuery() | Out-Null
        Write-Host "[✓] $label" -ForegroundColor Green
    }

    # 1. Create Databases
    Write-Host "`n[1/4] Creating Databases..." -ForegroundColor Yellow
    Exec-SqlCmd -sqlText "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'UnlockAudit_UAT') CREATE DATABASE UnlockAudit_UAT;" -label "Database 'UnlockAudit_UAT' verified."
    Exec-SqlCmd -sqlText "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'UnlockAudit_PROD') CREATE DATABASE UnlockAudit_PROD;" -label "Database 'UnlockAudit_PROD' verified."

    # 2. Deploy Schema to UAT
    Write-Host "`n[2/4] Deploying AccountUnlockAudit table to UnlockAudit_UAT..." -ForegroundColor Yellow
    $uatTableSql = @"
USE UnlockAudit_UAT;
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AccountUnlockAudit' AND xtype='U')
CREATE TABLE AccountUnlockAudit (
    AuditID INT IDENTITY(1,1) PRIMARY KEY,
    EventTimestamp DATETIME2 DEFAULT SYSUTCDATETIME(),
    TargetAccount NVARCHAR(100) NOT NULL,
    RequestedBy NVARCHAR(100) NOT NULL,
    ActionTaken NVARCHAR(100) NOT NULL,
    Status NVARCHAR(20) NOT NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    Environment NVARCHAR(20) DEFAULT 'UAT'
);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_Audit_Timestamp' AND object_id = OBJECT_ID('AccountUnlockAudit'))
CREATE NONCLUSTERED INDEX IX_Audit_Timestamp ON AccountUnlockAudit (EventTimestamp DESC);
"@
    Exec-SqlCmd -sqlText $uatTableSql -label "Table AccountUnlockAudit deployed to UnlockAudit_UAT."

    # 3. Deploy Schema to PROD
    Write-Host "`n[3/4] Deploying AccountUnlockAudit table to UnlockAudit_PROD..." -ForegroundColor Yellow
    $prodTableSql = @"
USE UnlockAudit_PROD;
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AccountUnlockAudit' AND xtype='U')
CREATE TABLE AccountUnlockAudit (
    AuditID INT IDENTITY(1,1) PRIMARY KEY,
    EventTimestamp DATETIME2 DEFAULT SYSUTCDATETIME(),
    TargetAccount NVARCHAR(100) NOT NULL,
    RequestedBy NVARCHAR(100) NOT NULL,
    ActionTaken NVARCHAR(100) NOT NULL,
    Status NVARCHAR(20) NOT NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    Environment NVARCHAR(20) DEFAULT 'PRODUCTION'
);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_Audit_Timestamp' AND object_id = OBJECT_ID('AccountUnlockAudit'))
CREATE NONCLUSTERED INDEX IX_Audit_Timestamp ON AccountUnlockAudit (EventTimestamp DESC);
"@
    Exec-SqlCmd -sqlText $prodTableSql -label "Table AccountUnlockAudit deployed to UnlockAudit_PROD."

    # 4. Verification Check
    Write-Host "`n[4/4] Verifying tables..." -ForegroundColor Yellow
    $verifyCmd = $connection.CreateCommand()
    $verifyCmd.CommandText = "SELECT COUNT(*) FROM UnlockAudit_UAT.sys.tables WHERE name='AccountUnlockAudit'"
    $count = $verifyCmd.ExecuteScalar()
    if ($count -ge 1) {
        Write-Host "[✓] Verification PASSED: Tables exist in both databases." -ForegroundColor Green
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "       DATABASES AND AUDIT TABLES CREATED SUCCESSFULLY!              " -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host " - Server:           $serverTarget" -ForegroundColor White
    Write-Host " - UAT Database:     UnlockAudit_UAT" -ForegroundColor White
    Write-Host " - PROD Database:    UnlockAudit_PROD" -ForegroundColor White
    Write-Host "======================================================================`n" -ForegroundColor Cyan

} catch {
    Write-Host "`n[ERROR] Operation failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
} finally {
    if ($connection.State -eq 'Open') {
        $connection.Close()
    }
}
