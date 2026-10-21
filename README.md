# First Assurance - IT Account Unlock Automation System
> **Insure • Secure • Assure** | Enterprise Active Directory Self-Service Chatbot for Microsoft Teams

An automated, self-service IT support solution designed for **First Assurance Kenya**. This system allows corporate employees to securely unlock their locked Windows Active Directory domain accounts directly from **Microsoft Teams** in seconds, eliminating manual IT Help Desk tickets while maintaining full security compliance, audit logging, rate limiting, and optional Two-Factor Authentication (2FA).

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [End-to-End Workflow](#end-to-end-workflow)
3. [API Routes & Endpoints](#api-routes--endpoints)
4. [Security & Compliance Controls](#security--compliance-controls)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Local Development & Execution Guide](#local-development--execution-guide)
7. [Directory Structure](#directory-structure)
8. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## System Architecture

```mermaid
flowchart TD
    subgraph Client["Employee Workstations & Mobile"]
        TeamsClient["Microsoft Teams App\n(Desktop, Mobile, Web)"]
    end

    subgraph CloudRelay["Microsoft Cloud & Relay"]
        TeamsCloud["Microsoft Teams Bot Framework\n(smba.trafficmanager.net)"]
        DevTunnel["Microsoft Dev Tunnel\n(spiffy-fog-m1hf0t6.uks1)"]
    end

    subgraph AppServer["Account Unlock Application Server"]
        subgraph TeamsBot["Teams Bot Service (:3978)"]
            FastAPIAdapter["FastAPI / Uvicorn Server"]
            AuthValidator["Entra ID Token Validator"]
            SessionManager["Session & State Machine\n(teams_session.py)"]
            AdaptiveCards["Branded Adaptive Cards Engine\n(#F78723 Orange Palette)"]
            StaticAssets["Asset Server (/static)\n(first_assurance_logo.png)"]
        end

        subgraph RestAPI["Backend REST API (:8000)"]
            SwaggerUI["Swagger UI (/docs)"]
            APIRouter["API Router (/api/account/*)"]
        end

        subgraph CoreServices["Shared Enterprise Services"]
            ADService["AD Service Dispatcher\n(real_ad_service.py / mock)"]
            TwoFactor["2FA Service\n(RFC 6238 TOTP / Authenticator)"]
            AuditEngine["Audit & Rate Limit Engine\n(audit_db.py)"]
        end
    end

    subgraph EnterpriseInfra["Corporate Enterprise Infrastructure"]
        DomainController[("Active Directory DC\n172.17.0.220:389\nLDAP / NTLM / Kerberos")]
        PostgresDB[("PostgreSQL Audit DB\nfa-postgresdb:5432\nAudit Trails & Rate Limits")]
    end

    TeamsClient <-->|HTTPS Messaging| TeamsCloud
    TeamsCloud <-->|Webhook /api/messages| DevTunnel
    DevTunnel <-->|Local Relay :3978| FastAPIAdapter

    FastAPIAdapter --> AuthValidator --> SessionManager
    SessionManager --> AdaptiveCards
    SessionManager --> CoreServices
    APIRouter --> CoreServices

    ADService <-->|LDAP Modify lockoutTime=0| DomainController
    AuditEngine <-->|SQL Queries & Inserts| PostgresDB
```

### Component Roles

| Component | Port | Purpose |
| :--- | :--- | :--- |
| **Microsoft Teams Bot** ([`bot/teams_app.py`](file:///c:/Users/nkibe/Desktop/account-unlock-system/bot/teams_app.py)) | `3978` | Receives incoming Webhook activities from Microsoft Teams, validates Entra ID app credentials, renders branded Adaptive Cards, dispatches typing indicators, and tracks user conversation state. |
| **REST Backend & Swagger** ([`backend/main.py`](file:///c:/Users/nkibe/Desktop/account-unlock-system/backend/main.py)) | `8000` | Exposes REST endpoints for administrative tools, third-party system integrations, monitoring health checks, and interactive Swagger documentation at `/docs`. |
| **Dev Tunnel** (`devtunnel.exe`) | `3978` | Provides a secure, persistent TLS bridge from the Microsoft Teams cloud to the local development server (`https://vrt0glbb-3978.uks1.devtunnels.ms`). In production, this is replaced with an enterprise reverse proxy. |
| **Active Directory Integration** ([`real_ad_service.py`](file:///c:/Users/nkibe/Desktop/account-unlock-system/backend/services/real_ad_service.py)) | `389` (LDAP) | Connects to First Assurance domain controllers (`172.17.0.220`) to query user account lock status (`lockoutTime`) and execute unlocks. |
| **Audit Database** ([`audit_db.py`](file:///c:/Users/nkibe/Desktop/account-unlock-system/backend/database/audit_db.py)) | `5432` | Tracks every attempt, requester identity, target employee, and outcome in PostgreSQL (with automatic SQLite fallback) for compliance and rate limiting. |

---

## End-to-End Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Employee (Teams User)
    participant Teams as Microsoft Teams
    participant Bot as Teams Bot (:3978)
    participant AD as Active Directory (LDAP)
    participant DB as Audit DB (PostgreSQL)

    Employee->>Teams: Sends "Hello Bot" or "1"
    Teams->>Bot: POST /api/messages (Activity)
    Bot->>Teams: Typing Indicator + Welcome Card (Brand Banner)
    Teams->>Employee: Displays Branded Menu Card

    Employee->>Teams: Enters Employee Name (e.g., "Newton Kibe")
    Teams->>Bot: POST /api/messages (Text input)
    Bot->>DB: Check daily unlock rate limit (max 3/day)
    DB-->>Bot: Limit OK (Attempts: 0/3)
    Bot->>AD: Query user sAMAccountName / displayName & lockoutTime
    AD-->>Bot: User found, lockoutTime > 0 (Locked)
    Bot->>DB: Log ACCOUNT_VERIFIED audit record
    Bot->>Teams: Verification Card (Name, Dept, "Locked 🔒", Orange Action Block)
    Teams->>Employee: Prompts: "Would you like me to unlock your account?"

    alt 2FA is ENABLED
        Employee->>Teams: Clicks "🔓 Yes, Unlock Account"
        Bot->>Teams: Two-Factor Authentication Card
        Employee->>Teams: Enters 6-digit Authenticator Code
        Bot->>Bot: Verify RFC 6238 TOTP code
    end

    Employee->>Teams: Clicks "🔓 Unlock Account"
    Teams->>Bot: POST /api/messages (SubmitAction)
    Bot->>AD: LDAP Modify (lockoutTime = 0)
    AD-->>Bot: Success
    Bot->>DB: Log UNLOCK_SUCCESS audit record
    Bot->>Teams: Success Card ("Account Unlocked 🎉", Status: Active 🟢)
    Teams->>Employee: "Your account has been successfully unlocked!"
```

---

## API Routes & Endpoints

### 1. Teams Bot Service (`bot/teams_app.py` on Port `3978`)

| Route | Method | Description | Request Payload / Response |
| :--- | :---: | :--- | :--- |
| `/api/messages` | `POST` | Core Bot Framework webhook receiving all chat activities, card submit actions, and conversation updates from Microsoft Teams. | Handled via Microsoft Teams Python SDK (`ActivityContext`). Returns HTTP `200 OK` on processing. |
| `/static/{filename}` | `GET` | Serves First Assurance corporate brand assets (e.g. `first_assurance_logo.png`) directly to Teams clients and webhooks. | Image file bytes (`image/png`). |

---

### 2. REST Backend Service (`backend/main.py` on Port `8000`)

Interactive documentation is available at:
* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`

#### `GET /`
* **Description:** Health check and service status.
* **Response:**
  ```json
  {
    "system": "Account Unlock Automation System",
    "status": "online"
  }
  ```

#### `GET /api/account/status/{username}`
* **Description:** Query user details and account lock status from Active Directory.
* **Parameters:** `username` (string, path parameter — e.g. `nkibe` or `EMP001`)
* **Response (Locked User):**
  ```json
  {
    "success": true,
    "account": {
      "employee_id": "nkibe",
      "name": "Newton Kibe",
      "email": "nkibe@firstassurance.co.ke",
      "department": "Information Technology",
      "locked": true,
      "failed_attempts": 3
    }
  }
  ```

#### `POST /api/account/unlock`
* **Description:** Programmatically unlock an Active Directory account.
* **Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "username": "nkibe"
  }
  ```
* **Response:**
  ```json
  {
    "success": true,
    "username": "NKIBE",
    "user": "Newton Kibe",
    "message": "Account successfully unlocked in Active Directory.",
    "status": "unlocked"
  }
  ```

#### `GET /api/account/audit-logs`
* **Description:** Retrieve audit records from PostgreSQL / SQLite.
* **Query Parameters:**
  * `environment` (optional, default `"uat"`)
  * `limit` (optional, default `50`)
* **Response:**
  ```json
  {
    "success": true,
    "environment": "uat",
    "count": 1,
    "logs": [
      {
        "id": 104,
        "timestamp": "2026-10-15T08:43:22",
        "action": "UNLOCK_SUCCESS",
        "requester_name": "Newton Kibe",
        "target_account_id": "nkibe",
        "target_account_name": "Newton Kibe",
        "target_department": "Information Technology",
        "status": "SUCCESS",
        "details": "Account successfully unlocked in Active Directory."
      }
    ]
  }
  ```

---

## Security & Compliance Controls

1. **Microsoft Entra ID Zero-Trust Identity Validation:**
   * Automatically extracts and validates employee identity claims (`aad_object_id`, `userPrincipalName`, `email`, `displayName`) directly from Microsoft Teams' Entra ID authenticated session.
   * **Zero-2FA Frictionless Self-Unlock:** When an employee unlocks their own account from Teams, Entra ID has already authenticated them with company credentials and MFA. The bot provides a **1-click instant unlock with zero 2FA code entry**.
   * **Adaptive Colleague Protection:** If an employee attempts to unlock an account on behalf of a colleague from a shared workstation, the bot logs both identities in the audit database and can conditionally enforce 2FA verification.
2. **Daily Rate Limiting (Brute-Force Protection):**
   * Limits every user to a maximum of **3 unlock requests within a 24-hour window**.
   * If a user exceeds 3 requests, the bot automatically transitions to a locked-out state and presents the **IT Service Desk Referral Card** with direct contact information (`ithelpdesk@firstassurance.co.ke`, Ext 4444).
3. **Immutable Audit Trail:**
   * Every query, verification failure, cancel click, and unlock execution is recorded in the PostgreSQL database.
   * Logs include the requesting Teams user ID & name alongside the target employee ID, ensuring full attribution even if an employee uses the bot from a colleague's workstation.
4. **Enterprise 2FA Fallback (RFC 6238 TOTP):**
   * Built-in support for **Microsoft Authenticator** and **Google Authenticator**.
   * Can be toggled **ON** or **OFF** system-wide by an IT Administrator at runtime by typing `2fa on` or `2fa off` directly in Microsoft Teams or updating `.env`.
4. **Corporate Visual Identity & Theme:**
   * Styled according to First Assurance's official brand guidelines (`#F78723` warm orange palette).
   * Standard Microsoft Teams Royal Blue buttons have been removed in favor of native orange action blocks (`style="warning"`) to provide an authentic company look and feel.

---

## Environment Variables Reference

Create a `.env` file in the project root directory. Below is the complete configuration:

```ini
# ============================================================
# Environment & Data Source Mode
# ============================================================
# ENVIRONMENT: 'PRODUCTION' (Real Data) or 'UAT' (Mock testing)
ENVIRONMENT=PRODUCTION

# DATA_SOURCE: 'real' (Live Active Directory) or 'mock' (In-memory mock store)
DATA_SOURCE=real

# ============================================================
# Audit Database (PostgreSQL with SQLite fallback)
# ============================================================
DATABASE_URL=postgresql://unlock_user:your_password_here@localhost:5432/unlock

# ============================================================
# Microsoft Teams Bot Registration (Azure Portal / Bot Framework)
# ============================================================
# Azure App Client ID (Application ID)
CLIENT_ID=d14110fe-3594-4462-a9be-0bd8c2c421c0

# Azure App Client Secret (Obtained from Azure Portal App Registrations)
CLIENT_SECRET=your_azure_client_secret_here

# Microsoft Entra ID Directory (Tenant) ID
TENANT_ID=e36edb0e-9e2d-466b-97ea-1d4259aa42ee

# Local HTTP Server Port
PORT=3978

# Enforce signature validation (false in production)
DANGEROUSLY_ALLOW_UNAUTHENTICATED_REQUESTS=false

# ============================================================
# Active Directory (Domain Controller Configuration)
# ============================================================
AD_LDAP_SERVER=ldap://172.17.0.220:389
AD_DOMAIN=firstassurance.co.ke
AD_BASE_DN=DC=firstassurance,DC=co,DC=ke
AD_BIND_USER=nkibe
AD_BIND_PASSWORD=your_ad_service_account_password_here

# ============================================================
# Security Policies
# ============================================================
# Set to 'false' for frictionless 1-click unlock during demos
# Set to 'true' to require 6-digit Authenticator app code
ENABLE_2FA=false
```

---

## Local Development & Execution Guide

### Prerequisites
* Python 3.10+ (Tested on Python 3.12 64-bit on Windows)
* Microsoft Dev Tunnel CLI (`winget install Microsoft.devtunnel`)
* Active connection to First Assurance internal network or VPN (for LDAP & DB)

### 1. Installation
```powershell
# Clone the repository
git clone <repo-url>
cd account-unlock-system

# Install Python dependencies
pip install -r requirements.txt
```

---

### 2. Running the System (3 Methods)

#### Method A: 1-Click Desktop Batch Scripts (Recommended)
* **To Start Everything:** Double-click [`start_all.bat`](file:///c:/Users/nkibe/Desktop/account-unlock-system/start_all.bat).
  * Opens 3 dedicated console windows: Dev Tunnel, Teams Bot, and Backend API.
* **To Stop Everything:** Double-click [`stop_all.bat`](file:///c:/Users/nkibe/Desktop/account-unlock-system/stop_all.bat).
  * Automatically terminates all background processes and frees ports `3978` and `8000`.

#### Method B: VS Code Tasks
* Press **`Ctrl + Shift + B`** in VS Code (or menu `Terminal` ➔ `Run Build Task...`).
* Select **`Start All Services`**. VS Code will launch the Dev Tunnel, Teams Bot, and Backend API in parallel split terminal panes.
* Press **`F5`** to launch the Teams Bot with interactive breakpoint debugging.

#### Method C: Manual Terminal Execution
Open 3 separate terminal tabs:

* **Terminal 1 (Dev Tunnel Relay):**
  ```powershell
  devtunnel host spiffy-fog-m1hf0t6
  ```
* **Terminal 2 (Teams Bot Server):**
  ```powershell
  python bot/teams_app.py
  ```
* **Terminal 3 (REST API & Swagger - Optional):**
  ```powershell
  python -m uvicorn backend.main:app --reload --port 8000
  ```

---

## Directory Structure

```text
account-unlock-system/
│
├── .vscode/                      # VS Code automation
│   ├── launch.json               # F5 Debug configuration with pre-launch tunnel
│   └── tasks.json                # Ctrl+Shift+B Build task configurations
│
├── assets/                       # Corporate brand assets
│   └── first_assurance_logo.png  # High-resolution First Assurance banner logo
│
├── backend/                      # Backend services and APIs
│   ├── database/
│   │   └── audit_db.py           # PostgreSQL/SQLite audit logging & rate limiter
│   ├── routes/
│   │   └── unlock.py             # REST endpoints (/status, /unlock, /audit-logs)
│   ├── services/
│   │   ├── ad_service.py         # AD service facade with mock/real switcher
│   │   ├── mock_ad_service.py    # Offline in-memory Active Directory mock
│   │   ├── real_ad_service.py    # Production LDAP Active Directory integration
│   │   └── two_factor_service.py # RFC 6238 TOTP Microsoft Authenticator engine
│   └── main.py                   # FastAPI REST backend gateway (:8000)
│
├── bot/                          # Microsoft Teams Bot implementation
│   ├── cards.py                  # First Assurance branded Adaptive Card builders
│   ├── conversation.py           # Finite state machine and dialog logic
│   ├── responses.py              # Bot conversational string templates
│   ├── teams_app.py              # Main bot server & webhook entrypoint (:3978)
│   ├── teams_session.py          # User session store and activity router
│   └── theme.py                  # Corporate color palette and logo URLs
│
├── data/                         # Local database fallbacks & secrets storage
│   ├── audit_log.db              # SQLite local audit database
│   └── totp_secrets.json         # Encrypted/Base32 authenticator secrets
│
├── start_all.bat                 # 1-click startup script for all services
├── stop_all.bat                  # 1-click cleanup script for all processes
├── requirements.txt              # Python project dependencies
├── .env.example                  # Environment configuration template
└── README.md                     # Comprehensive project documentation
```

---

## Troubleshooting & FAQs

### Q1: `Client error '401 Unauthorized'` when bot tries to send a message
* **Cause:** `TENANT_ID` is missing, empty, or mismatched in `.env`.
* **Fix:** Verify that `TENANT_ID=e36edb0e-9e2d-466b-97ea-1d4259aa42ee` in `.env` and restart the bot server.

### Q2: `[Errno 10048] error while attempting to bind on address`
* **Cause:** Another process or earlier terminal is already listening on port `3978` or `8000`.
* **Fix:** Double-click [`stop_all.bat`](file:///c:/Users/nkibe/Desktop/account-unlock-system/stop_all.bat) to terminate all lingering processes, or run:
  ```powershell
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 3978).OwningProcess -Force
  ```

### Q3: `WAM Error: NoNetwork` when launching `devtunnel`
* **Cause:** Windows Web Account Manager cannot reach Microsoft authentication servers (e.g., system just booted before Wi-Fi or corporate network connected).
* **Fix:** Ensure your internet connection is active, then run:
  ```powershell
  devtunnel user show
  devtunnel host spiffy-fog-m1hf0t6
  ```

### Q4: Why are Teams buttons not blue?
* Standard Microsoft Teams `style="positive"` automatically renders buttons in Teams Royal Blue (`#5B5FC7`). To align with First Assurance’s brand identity, we removed `style="positive"` and implemented clickable in-body containers with `style="warning"`, rendering in the authentic First Assurance warm amber/orange `#F78723`.
