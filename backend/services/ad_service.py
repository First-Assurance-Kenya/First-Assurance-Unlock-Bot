import logging
import os
from typing import Any, Dict, Optional

from backend.services.mock_ad_service import MockAccountService

logger = logging.getLogger("account-unlock-service")

# Global singleton mock service
_mock_service = MockAccountService()
mock_users = _mock_service.mock_users


def get_data_source() -> str:
    """Return the active data source: 'mock' (default) or 'real'."""
    return os.getenv("DATA_SOURCE", "mock").strip().lower()


def is_mock_mode() -> bool:
    """Return True if running in MOCK mode."""
    return get_data_source() != "real"


def get_ldap_connection():
    """
    Direct LDAP connection helper.
    SAFETY GUARD: If DATA_SOURCE=mock, refuses to connect and raises an error.
    """
    if is_mock_mode():
        raise PermissionError("Real AD access is disabled in MOCK mode.")

    from backend.services.real_ad_service import RealActiveDirectoryService
    return RealActiveDirectoryService().get_connection()


def find_user(username: str) -> Optional[Dict[str, Any]]:
    """Look up an account by employee ID or username."""
    if is_mock_mode():
        return _mock_service.find_user(username)

    from backend.services.real_ad_service import RealActiveDirectoryService
    return RealActiveDirectoryService().find_user(username)


def find_user_by_name(full_name: str) -> Optional[Dict[str, Any]]:
    """Look up an account by user full/display name."""
    if is_mock_mode():
        return _mock_service.find_user_by_name(full_name)

    from backend.services.real_ad_service import RealActiveDirectoryService
    return RealActiveDirectoryService().find_user_by_name(full_name)


def get_account_status(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve status dictionary for the given account."""
    if is_mock_mode():
        return _mock_service.get_account_status(username)

    from backend.services.real_ad_service import RealActiveDirectoryService
    user = RealActiveDirectoryService().find_user(username)
    if not user:
        return None
    return {
        "employee_id": user["employee_id"],
        "name": user["name"],
        "email": user["email"],
        "department": user["department"],
        "locked": user["locked"],
        "failed_attempts": user["failed_attempts"],
    }


def unlock_account(username: str) -> Dict[str, Any]:
    """
    Unlock user account.
    In MOCK mode: Modifies ONLY the local in-memory mock repository.
    In REAL mode: Connects to Active Directory and modifies lockoutTime.
    """
    if is_mock_mode():
        return _mock_service.unlock_account(username)

    from backend.services.real_ad_service import RealActiveDirectoryService
    return RealActiveDirectoryService().unlock_account(username)


def lock_account(username: str) -> bool:
    """Lock an account in the mock store."""
    if is_mock_mode():
        return _mock_service.lock_account(username)
    raise NotImplementedError("Manual locking is not supported on live Active Directory.")


def reset_all_accounts_to_locked() -> None:
    """Reset all mock accounts to locked status for demo and test repeatability."""
    _mock_service.reset_all_accounts_to_locked()