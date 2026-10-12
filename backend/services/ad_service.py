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


# Simulated locked accounts set for test and demo repeatability
# Holds lowercase usernames/sAMAccountNames or employee IDs
_simulated_locked_accounts = {"nkibe"}


def set_account_locked(username: str, is_locked: bool = True) -> None:
    """Manually mark or unmark an account as simulated locked for testing."""
    u = username.strip().lower()
    if is_locked:
        _simulated_locked_accounts.add(u)
    else:
        _simulated_locked_accounts.discard(u)


def is_account_simulated_locked(username: str) -> bool:
    """Check if an account is currently marked as simulated locked."""
    return username.strip().lower() in _simulated_locked_accounts


def find_user(username: str) -> Optional[Dict[str, Any]]:
    """Look up an account by employee ID or username."""
    if is_mock_mode():
        user = _mock_service.find_user(username)
    else:
        from backend.services.real_ad_service import RealActiveDirectoryService
        user = RealActiveDirectoryService().find_user(username)

    if user:
        emp_id = user.get("employee_id", "").strip().lower()
        uname = username.strip().lower()
        if emp_id in _simulated_locked_accounts or uname in _simulated_locked_accounts:
            user["locked"] = True
            user["failed_attempts"] = max(user.get("failed_attempts", 0), 3)
    return user


def find_user_by_name(full_name: str) -> Optional[Dict[str, Any]]:
    """Look up an account by user full/display name."""
    if is_mock_mode():
        user = _mock_service.find_user_by_name(full_name)
    else:
        from backend.services.real_ad_service import RealActiveDirectoryService
        user = RealActiveDirectoryService().find_user_by_name(full_name)

    if user:
        emp_id = user.get("employee_id", "").strip().lower()
        name_lower = user.get("name", "").strip().lower()
        if emp_id in _simulated_locked_accounts or any(acc in name_lower for acc in _simulated_locked_accounts):
            user["locked"] = True
            user["failed_attempts"] = max(user.get("failed_attempts", 0), 3)
    return user


def get_account_status(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve status dictionary for the given account."""
    user = find_user(username)
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


def search_users(query: str, limit: int = 15) -> list:
    """Search accounts by ID, username, name, or email matching query."""
    if is_mock_mode():
        cleaned = query.strip().lower()
        matches = []
        for u in mock_users.values():
            if (
                cleaned in u["employee_id"].lower()
                or cleaned in u["name"].lower()
                or cleaned in u.get("email", "").lower()
                or cleaned in u.get("department", "").lower()
            ):
                matches.append(u)
                if len(matches) >= limit:
                    break
        return matches

    from backend.services.real_ad_service import RealActiveDirectoryService
    users = RealActiveDirectoryService().search_users(query, limit)
    for u in users:
        emp_id = u.get("employee_id", "").strip().lower()
        name_lower = u.get("name", "").strip().lower()
        if emp_id in _simulated_locked_accounts or any(acc in name_lower for acc in _simulated_locked_accounts):
            u["locked"] = True
            u["failed_attempts"] = max(u.get("failed_attempts", 0), 3)
    return users


def unlock_account(username: str, force: bool = False) -> Dict[str, Any]:
    """
    Unlock user account.
    In MOCK mode: Modifies ONLY the local in-memory mock repository.
    In REAL mode: Connects to Active Directory and modifies lockoutTime.
    """
    _simulated_locked_accounts.discard(username.strip().lower())

    if is_mock_mode():
        return _mock_service.unlock_account(username)

    from backend.services.real_ad_service import RealActiveDirectoryService
    return RealActiveDirectoryService().unlock_account(username, force=force)


def lock_account(username: str) -> bool:
    """Lock an account in the mock store or mark as simulated locked for live testing."""
    u = username.strip().lower()
    _simulated_locked_accounts.add(u)
    if is_mock_mode():
        return _mock_service.lock_account(username)
    logger.info("Simulated lock applied to user '%s'.", username)
    return True


def reset_all_accounts_to_locked() -> None:
    """Reset all accounts to locked status for demo and test repeatability."""
    _simulated_locked_accounts.add("nkibe")
    _mock_service.reset_all_accounts_to_locked()