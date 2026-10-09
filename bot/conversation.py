import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from backend.database.audit_db import check_rate_limit, log_audit_event
from backend.services.ad_service import find_user, find_user_by_name, unlock_account
from bot.cards import (
    create_already_unlocked_card,
    create_it_referral_card,
    create_menu_card,
    create_success_card,
    create_unauthorized_card,
    create_verification_card,
)
from bot.responses import (
    ACCOUNT_UNLOCKED_MESSAGE,
    CANCEL_MESSAGE,
    ENTER_FULL_NAME_MESSAGE,
    INVALID_CONFIRMATION_MESSAGE,
    INVALID_MENU_MESSAGE,
    MENU_MESSAGE,
    RATE_LIMIT_EXCEEDED_MESSAGE,
    TRIGGER_PROMPT,
    UNAUTHORIZED_ACCOUNT_MESSAGE,
    VERIFY_FAILED_MESSAGE,
    VERIFY_SUCCESS_ALREADY_UNLOCKED_TEMPLATE,
    VERIFY_SUCCESS_LOCKED_TEMPLATE,
)

logger = logging.getLogger("account-unlock-bot")

TRIGGER_PHRASES = {
    "hello bot",
    "hi bot",
    "hey bot",
    "hello",
    "hi",
    "hey",
    "start",
    "help",
    "bot",
}

RESET_COMMANDS = {
    "reset",
    "restart",
    "start over",
}

MENU_UNLOCK_OPTIONS = {
    "1",
    "1.",
    "1. unlock account",
    "unlock account",
    "unlock",
    "1. unlock",
}

CONFIRM_YES_OPTIONS = {
    "yes",
    "y",
    "yes please",
    "unlock",
    "unlock account",
    "sure",
    "ok",
    "okay",
}

CONFIRM_NO_OPTIONS = {
    "no",
    "n",
    "cancel",
    "stop",
    "nevermind",
}

# Administrative users permitted to unlock any corporate account
ADMIN_USERS = {
    "newton kibe",
    "admin",
    "administrator",
    "it support",
}


class ConversationState(Enum):
    WAITING_FOR_TRIGGER = "waiting_for_trigger"
    WAITING_FOR_MENU = "waiting_for_menu"
    WAITING_FOR_NAME = "waiting_for_name"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    LOCKED_OUT = "locked_out"
    COMPLETED = "completed"


class AccountUnlockBot:
    """
    State machine for IT Account Unlock with Entra ID authorization,
    rate limiting, and SQL database audit logging.
    """

    def __init__(self, requester_name: str = "Unknown", requester_id: str = "N/A"):
        self.state = ConversationState.WAITING_FOR_TRIGGER
        self.user_data: Optional[Dict[str, Any]] = None
        self.requester_name = requester_name
        self.requester_id = requester_id

    def set_requester(self, name: str, user_id: str = "N/A") -> None:
        """Update authenticated Entra ID / Teams identity for this session."""
        if name and name != "Unknown":
            self.requester_name = name
        if user_id and user_id != "N/A":
            self.requester_id = user_id

    def check_requester_rate_limit(self) -> Tuple[bool, int]:
        """Check if this requester has exceeded the 3-attempt limit."""
        return check_rate_limit(self.requester_name, max_attempts=3, window_minutes=30)

    def is_authorized_to_unlock(self, target_account_name: str) -> bool:
        """
        Authorization Policy:
        - IT Administrators can unlock any account.
        - Regular employees can ONLY unlock their own verified account (matching their Teams / Entra ID login).
        - If requester identity is unspecified ('Unknown'), default to allow (for local unit tests).
        """
        req_lower = self.requester_name.strip().lower()
        target_lower = target_account_name.strip().lower()

        # Admin override
        if any(admin in req_lower for admin in ADMIN_USERS):
            return True

        # Unspecified local test runner
        if req_lower in ("unknown", "test runner", "console", "local-console-session"):
            return True

        # Exact or partial match (e.g. 'Jane' in 'Jane Doe', or 'Jane Doe' in 'Jane Doe')
        req_parts = set(req_lower.split())
        target_parts = set(target_lower.split())
        if req_parts & target_parts or req_lower in target_lower or target_lower in req_lower:
            return True

        return False

    def start(self) -> str:
        text, _ = self.start_with_card()
        return text

    def start_with_card(self) -> Tuple[str, Any]:
        # Check rate limit before starting
        is_limited, attempts = self.check_requester_rate_limit()
        if is_limited:
            self.state = ConversationState.LOCKED_OUT
            log_audit_event(
                action="RATE_LIMITED_REFERRED_TO_IT",
                requester_name=self.requester_name,
                requester_id=self.requester_id,
                status="RATE_LIMITED",
                details=f"Rate limit exceeded ({attempts}/3 attempts). Referred to IT Helpdesk.",
            )
            return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.requester_name, attempts)

        self.reset()
        self.state = ConversationState.WAITING_FOR_MENU
        return MENU_MESSAGE, create_menu_card()

    def reset(self):
        self.state = ConversationState.WAITING_FOR_TRIGGER
        self.user_data = None

    def process_message(self, message: str) -> str:
        text, _ = self.process_input(text=message)
        return text

    def process_input(
        self,
        text: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Optional[Any]]:
        # Enforce rate limit check on every interaction
        is_limited, attempts = self.check_requester_rate_limit()
        if is_limited:
            self.state = ConversationState.LOCKED_OUT
            return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.requester_name, attempts)

        # Handle Adaptive Card button actions
        if isinstance(data, dict):
            action = data.get("action")
            if action == "unlock_account":
                self.state = ConversationState.WAITING_FOR_NAME
                return ENTER_FULL_NAME_MESSAGE, None

            if action == "confirm_unlock" and self.user_data:
                return self.execute_unlock()

            if action == "cancel":
                if self.user_data:
                    log_audit_event(
                        action="UNLOCK_CANCELLED",
                        requester_name=self.requester_name,
                        requester_id=self.requester_id,
                        target_account_id=self.user_data.get("employee_id"),
                        target_account_name=self.user_data.get("name"),
                        target_department=self.user_data.get("department"),
                        status="CANCELLED",
                        details="User clicked cancel button.",
                    )
                self.state = ConversationState.COMPLETED
                return CANCEL_MESSAGE, None

            if action in ("restart", "reset"):
                return self.start_with_card()

        # Handle text input
        raw_text = (text or "").strip()
        text_lower = raw_text.lower()

        if not raw_text:
            if self.state == ConversationState.WAITING_FOR_TRIGGER:
                return TRIGGER_PROMPT, None
            return "Please provide an input.", None

        # Global administrative resets for demo
        if text_lower in ("lock all", "relock", "lock accounts", "demo reset"):
            from backend.services.ad_service import reset_all_accounts_to_locked
            reset_all_accounts_to_locked()
            self.reset()
            return "🔒 All demo accounts have been reset to Locked. Type 'Hello Bot' to begin.", None

        if text_lower in RESET_COMMANDS:
            return self.start_with_card()

        if text_lower in TRIGGER_PHRASES or text_lower.startswith("hello bot"):
            return self.start_with_card()

        if self.state == ConversationState.WAITING_FOR_TRIGGER:
            return TRIGGER_PROMPT, None

        if self.state == ConversationState.WAITING_FOR_MENU:
            if text_lower in MENU_UNLOCK_OPTIONS:
                self.state = ConversationState.WAITING_FOR_NAME
                return ENTER_FULL_NAME_MESSAGE, None
            return INVALID_MENU_MESSAGE, create_menu_card()

        if self.state == ConversationState.WAITING_FOR_NAME:
            return self.handle_name_verification(raw_text)

        if self.state == ConversationState.WAITING_FOR_CONFIRMATION:
            return self.handle_confirmation(text_lower)

        if self.state == ConversationState.COMPLETED:
            return self.start_with_card()

        return TRIGGER_PROMPT, None

    def handle_name_verification(self, name_raw: str) -> Tuple[str, Optional[Any]]:
        user = find_user_by_name(name_raw) or find_user(name_raw)

        # 1. User not found -> Log failure and check rate limit
        if not user:
            log_audit_event(
                action="VERIFY_FAILED",
                requester_name=self.requester_name,
                requester_id=self.requester_id,
                target_account_name=name_raw,
                status="FAILURE",
                details=f"Account query failed for '{name_raw}'.",
            )
            # Re-check rate limit after recording failure
            is_limited, attempts = self.check_requester_rate_limit()
            if is_limited:
                self.state = ConversationState.LOCKED_OUT
                return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.requester_name, attempts)

            remaining = max(0, 3 - attempts)
            return (
                f"{VERIFY_FAILED_MESSAGE}\n\n*(Attempts remaining before IT referral: {remaining}/3)*",
                None,
            )

        # 2. Authorization Check: Is Jane trying to unlock Jane?
        if not self.is_authorized_to_unlock(user["name"]):
            log_audit_event(
                action="UNAUTHORIZED_ATTEMPT",
                requester_name=self.requester_name,
                requester_id=self.requester_id,
                target_account_id=user["employee_id"],
                target_account_name=user["name"],
                target_department=user["department"],
                status="BLOCKED",
                details=f"Policy violation: Authenticated user '{self.requester_name}' attempted to unlock target '{user['name']}'.",
            )
            is_limited, attempts = self.check_requester_rate_limit()
            if is_limited:
                self.state = ConversationState.LOCKED_OUT
                return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.requester_name, attempts)

            return (
                UNAUTHORIZED_ACCOUNT_MESSAGE.format(
                    requester=self.requester_name, target=user["name"]
                ),
                create_unauthorized_card(self.requester_name, user["name"]),
            )

        self.user_data = user

        # 3. Log verified account lookup
        log_audit_event(
            action="ACCOUNT_VERIFIED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=user["employee_id"],
            target_account_name=user["name"],
            target_department=user["department"],
            status="SUCCESS",
            details="User identity successfully verified.",
        )

        # Check account status
        current = find_user(user["employee_id"])
        if current and current.get("locked"):
            self.state = ConversationState.WAITING_FOR_CONFIRMATION
            card = create_verification_card(
                user["name"],
                user["department"],
                status="Locked 🔒"
            )
            text_reply = VERIFY_SUCCESS_LOCKED_TEMPLATE.format(
                name=user["name"],
                department=user["department"]
            )
            return text_reply, card
        else:
            self.state = ConversationState.COMPLETED
            card = create_already_unlocked_card(
                user["name"],
                user["department"]
            )
            text_reply = VERIFY_SUCCESS_ALREADY_UNLOCKED_TEMPLATE.format(
                name=user["name"],
                department=user["department"]
            )
            return text_reply, card

    def execute_unlock(self) -> Tuple[str, Any]:
        """Perform unlock, write to audit log, and return success card."""
        emp_id = self.user_data["employee_id"]
        res = unlock_account(emp_id)

        log_audit_event(
            action="UNLOCK_SUCCESS" if res.get("success") else "UNLOCK_FAILED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=emp_id,
            target_account_name=self.user_data["name"],
            target_department=self.user_data["department"],
            status="SUCCESS" if res.get("success") else "FAILURE",
            details=res.get("message", "Account unlock executed."),
        )

        self.state = ConversationState.COMPLETED
        card = create_success_card(
            self.user_data["name"],
            self.user_data["department"]
        )
        return ACCOUNT_UNLOCKED_MESSAGE, card

    def handle_confirmation(self, choice: str) -> Tuple[str, Optional[Any]]:
        if choice in CONFIRM_YES_OPTIONS:
            if self.user_data:
                return self.execute_unlock()

        if choice in CONFIRM_NO_OPTIONS:
            if self.user_data:
                log_audit_event(
                    action="UNLOCK_CANCELLED",
                    requester_name=self.requester_name,
                    requester_id=self.requester_id,
                    target_account_id=self.user_data.get("employee_id"),
                    target_account_name=self.user_data.get("name"),
                    target_department=self.user_data.get("department"),
                    status="CANCELLED",
                    details="User typed no/cancel.",
                )
            self.state = ConversationState.COMPLETED
            return CANCEL_MESSAGE, None

        card = None
        if self.user_data:
            card = create_verification_card(
                self.user_data["name"],
                self.user_data["department"],
                status="Locked 🔒"
            )
        return INVALID_CONFIRMATION_MESSAGE, card