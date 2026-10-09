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
        return {
            "success": False,
            "username": username,
            "message": "User account not found.",
            "status": "not_found"
        }

    result = unlock_account(username)

    return {
        "username": username,
        "user": user["name"],
        **result
    }