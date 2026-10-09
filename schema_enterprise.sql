-- ==============================================================================
-- Enterprise Microsoft SQL Server / Azure SQL DDL Script
-- First Assurance - IT Account Unlock Audit Database Schema
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- 1. UAT Database Setup
-- -----------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'AccountUnlock_UAT')
BEGIN
    CREATE DATABASE AccountUnlock_UAT;
    PRINT 'Database AccountUnlock_UAT created.';
END
GO

USE AccountUnlock_UAT;
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'AuditLogs')
BEGIN
    CREATE TABLE AuditLogs (
        Id BIGINT IDENTITY(1,1) PRIMARY KEY CLUSTERED,
        Timestamp DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        Action NVARCHAR(100) NOT NULL,
        RequesterName NVARCHAR(255) NOT NULL,
        RequesterId NVARCHAR(255) NULL,
        TargetAccountId NVARCHAR(100) NULL,
        TargetAccountName NVARCHAR(255) NULL,
        TargetDepartment NVARCHAR(150) NULL,
        Status NVARCHAR(50) NOT NULL,
        Environment NVARCHAR(50) NOT NULL,
        Details NVARCHAR(MAX) NULL
    );

    CREATE NONCLUSTERED INDEX IX_AuditLogs_Timestamp ON AuditLogs (Timestamp DESC);
    CREATE NONCLUSTERED INDEX IX_AuditLogs_Requester_Time ON AuditLogs (RequesterName, Timestamp DESC);
    CREATE NONCLUSTERED INDEX IX_AuditLogs_Target_Time ON AuditLogs (TargetAccountId, Timestamp DESC);

    PRINT 'Table AuditLogs and indexes created in AccountUnlock_UAT.';
END
GO


-- -----------------------------------------------------------------------------
-- 2. PRODUCTION Database Setup
-- -----------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'AccountUnlock_PROD')
BEGIN
    CREATE DATABASE AccountUnlock_PROD;
    PRINT 'Database AccountUnlock_PROD created.';
END
GO

USE AccountUnlock_PROD;
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'AuditLogs')
BEGIN
    CREATE TABLE AuditLogs (
        Id BIGINT IDENTITY(1,1) PRIMARY KEY CLUSTERED,
        Timestamp DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        Action NVARCHAR(100) NOT NULL,
        RequesterName NVARCHAR(255) NOT NULL,
        RequesterId NVARCHAR(255) NULL,
        TargetAccountId NVARCHAR(100) NULL,
        TargetAccountName NVARCHAR(255) NULL,
        TargetDepartment NVARCHAR(150) NULL,
        Status NVARCHAR(50) NOT NULL,
        Environment NVARCHAR(50) NOT NULL,
        Details NVARCHAR(MAX) NULL
    );

    CREATE NONCLUSTERED INDEX IX_AuditLogs_Timestamp ON AuditLogs (Timestamp DESC);
    CREATE NONCLUSTERED INDEX IX_AuditLogs_Requester_Time ON AuditLogs (RequesterName, Timestamp DESC);
    CREATE NONCLUSTERED INDEX IX_AuditLogs_Target_Time ON AuditLogs (TargetAccountId, Timestamp DESC);

    PRINT 'Table AuditLogs and indexes created in AccountUnlock_PROD.';
END
GO
