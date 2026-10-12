from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.ad_service import (
    find_user,
    get_account_status,
    unlock_account
)


router = APIRouter(
    prefix="/api/account",
    tags=["Account Unlock"]
)


class UnlockRequest(BaseModel):
    username: str


@router.get("/status/{username}")
def account_status(username: str):

    username = username.strip().upper()

    user = get_account_status(username)

    if not user:
        return {
            "success": False,
            "message": "User account not found."
        }

    return {
        "success": True,
        "account": user
    }


@router.post("/unlock")
def unlock_user(request: UnlockRequest):

    username = request.username.strip().upper()

    user = find_user(username)

    if not user:
        from backend.database.audit_db import log_audit_event

        log_audit_event(
            action="UNLOCK_FAILED",
            requester_name="API Gateway Client",
            status="FAILURE",
            target_account_id=username,
            details=f"User '{username}' not found via API Gateway."
        )
        return {
            "success": False,
            "username": username,
            "message": "User account not found.",
            "status": "not_found"
        }

    result = unlock_account(username)
    from backend.database.audit_db import log_audit_event

    log_audit_event(
        action="UNLOCK_SUCCESS",
        requester_name="API Gateway Client",
        status="SUCCESS" if result.get("success") else "FAILURE",
        target_account_id=user.get("employee_id"),
        target_account_name=user.get("name"),
        target_department=user.get("department"),
        details=result.get("message", "Account unlocked via API Gateway")
    )

    return {
        "username": username,
        "user": user["name"],
        **result
    }


@router.get("/audit-logs")
def view_audit_logs(environment: str = "uat", limit: int = 50):
    from backend.database.audit_db import get_audit_logs

    logs = get_audit_logs(limit=limit, environment=environment)
    return {
        "success": True,
        "environment": environment,
        "count": len(logs),
        "logs": logs
    }