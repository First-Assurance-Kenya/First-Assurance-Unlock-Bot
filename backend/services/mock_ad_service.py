from datetime import datetime
from typing import Any, Dict, Optional


def create_default_mock_users() -> Dict[str, Dict[str, Any]]:
    """Return a fresh dictionary of mock corporate accounts."""
    return {
        "EMP001": {
            "employee_id": "EMP001",
            "name": "Test Employee One",
            "email": "employee1@example.test",
            "department": "Information Technology",
            "locked": True,
            "failed_attempts": 5,
        },
        "EMP002": {
            "employee_id": "EMP002",
            "name": "Test Employee Two",
            "email": "employee2@example.test",
            "department": "Finance",
            "locked": False,
            "failed_attempts": 0,
        },
        "EMP003": {
            "employee_id": "EMP003",
            "name": "Test Employee Three",
            "email": "employee3@example.test",
            "department": "Human Resources",
            "locked": True,
            "failed_attempts": 5,
        },
        # Friendly aliases for testing existing conversational flows
        "JANE01": {
            "employee_id": "JANE01",
            "name": "Jane Doe",
            "email": "jane.doe@example.test",
            "department": "Human Resources",
            "locked": True,
            "failed_attempts": 5,
        },
        "ALEX01": {
            "employee_id": "ALEX01",
            "name": "Alex Johnson",
            "email": "alex.johnson@example.test",
            "department": "Finance",
            "locked": True,
            "failed_attempts": 5,
        },
        "NEWTON01": {
            "employee_id": "NEWTON01",
            "name": "Newton Kibe",
            "email": "newton.kibe@example.test",
            "department": "Information Technology",
            "locked": True,
            "failed_attempts": 5,
        },
    }


class MockAccountService:
    """Completely isolated in-memory account repository for development and testing."""

    def __init__(self):
        self.mock_users: Dict[str, Dict[str, Any]] = create_default_mock_users()

    def find_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Find user by employee_id or username (case-insensitive)."""
        if not username:
            return None
        return self.mock_users.get(username.strip().upper())

    def find_user_by_name(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Find user by display/full name (case-insensitive)."""
        if not full_name:
            return None
        cleaned_lower = full_name.strip().lower()
        for user in self.mock_users.values():
            if user["name"].strip().lower() == cleaned_lower:
                return user
        return None

    def get_account_status(self, username: str) -> Optional[Dict[str, Any]]:
        """Return account status dict without modifying state."""
        user = self.find_user(username)
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

    def unlock_account(self, username: str) -> Dict[str, Any]:
        """
        Unlock user account strictly in memory.
        Modifies ONLY the local mock repository.
        """
        user = self.find_user(username)
        if not user:
            return {
                "success": False,
                "message": "User account not found.",
                "status": "not_found",
            }

        if not user["locked"]:
            return {
                "success": True,
                "message": "Account is already unlocked.",
                "status": "already_unlocked",
            }

        user["locked"] = False
        user["failed_attempts"] = 0

        return {
            "success": True,
            "message": "Account successfully unlocked (Mock Environment).",
            "status": "unlocked",
            "unlocked_at": datetime.now().isoformat(),
        }

    def lock_account(self, username: str) -> bool:
        """Lock account strictly in memory."""
        user = self.find_user(username)
        if user:
            user["locked"] = True
            user["failed_attempts"] = 5
            return True
        return False

    def reset_all_accounts_to_locked(self) -> None:
        """Reset mock accounts to locked status for repeatable testing."""
        for user in self.mock_users.values():
            user["locked"] = True
            user["failed_attempts"] = 5
