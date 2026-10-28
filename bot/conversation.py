import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from backend.database.audit_db import (
    check_colleague_sponsorship_limit,
    check_rate_limit,
    get_sponsored_colleagues_today,
    log_audit_event,
)
from backend.services.ad_service import find_user, find_user_by_name, unlock_account
from backend.services.two_factor_service import (
    generate_otp,
    get_active_otp,
    get_totp_qr_url,
    get_totp_secret,
    is_2fa_enabled,
    mask_phone_number,
    set_2fa_enabled,
    set_totp_secret,
    verify_otp,
)
from bot.cards import (
    create_2fa_card,
    create_2fa_toggle_card,
    create_already_unlocked_card,
    create_it_referral_card,
    create_menu_card,
    create_success_card,
    create_totp_setup_card,
    create_unauthorized_card,
    create_verification_card,
)
from bot.responses import (
    ACCOUNT_UNLOCKED_MESSAGE,
    CANCEL_MESSAGE,
    COLLEAGUE_DAILY_LIMIT_EXCEEDED_MESSAGE,
    COLLEAGUE_MULTIPLE_EMPLOYEES_BLOCKED_MESSAGE,
    COLLEAGUE_VERIFY_FAILED_MESSAGE,
    ENTER_2FA_CODE_MESSAGE,
    ENTER_COLLEAGUE_NAME_MESSAGE,
    ENTER_FULL_NAME_MESSAGE,
    INVALID_CONFIRMATION_MESSAGE,
    INVALID_MENU_MESSAGE,
    MENU_MESSAGE,
    RATE_LIMIT_EXCEEDED_MESSAGE,
    TRIGGER_PROMPT,
    TWO_FACTOR_INVALID_CODE_TEMPLATE,
    TWO_FACTOR_MAX_ATTEMPTS_MESSAGE,
    TWO_FACTOR_TOGGLE_OFF_MESSAGE,
    TWO_FACTOR_TOGGLE_ON_MESSAGE,
    TWO_FACTOR_VERIFIED_MESSAGE,
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
    "nkibe",
    "newton",
    "admin",
    "administrator",
    "it support",
}



class ConversationState(Enum):
    WAITING_FOR_TRIGGER = "waiting_for_trigger"
    WAITING_FOR_MENU = "waiting_for_menu"
    WAITING_FOR_NAME = "waiting_for_name"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    WAITING_FOR_2FA = "waiting_for_2fa"
    LOCKED_OUT = "locked_out"
    COMPLETED = "completed"


class AccountUnlockBot:
    """
    State machine for IT Account Unlock with Entra ID authorization,
    rate limiting, and SQL database audit logging.
    """

    def __init__(
        self,
        requester_name: str = "Unknown",
        requester_id: str = "N/A",
        requester_email: Optional[str] = None,
        requester_upn: Optional[str] = None,
        requester_aad_id: Optional[str] = None,
    ):
        self.state = ConversationState.WAITING_FOR_TRIGGER
        self.user_data: Optional[Dict[str, Any]] = None
        self.requester_name = requester_name
        self.requester_id = requester_id
        self.requester_email = requester_email
        self.requester_upn = requester_upn
        self.requester_aad_id = requester_aad_id
        self.is_assisting_colleague: bool = False

    def set_requester(
        self,
        name: str,
        user_id: str = "N/A",
        email: Optional[str] = None,
        upn: Optional[str] = None,
        aad_id: Optional[str] = None,
    ) -> None:
        """Update authenticated Entra ID / Teams identity for this session."""
        if name and name != "Unknown":
            self.requester_name = name
        if user_id and user_id != "N/A":
            self.requester_id = user_id
        if email:
            self.requester_email = email
        if upn:
            self.requester_upn = upn
        if aad_id:
            self.requester_aad_id = aad_id

    def is_admin(self) -> bool:
        """Check if the session requester is a recognized IT administrator."""
        clean_name = (self.requester_name or "").strip().lower()
        clean_id = (self.requester_id or "").strip().lower()

        if clean_name in ADMIN_USERS or clean_id in ADMIN_USERS:
            return True

        # Check environment variable overrides (e.g. ADMIN_USERS="nkibe,newton.kibe@firstassurance.co.ke")
        import os
        env_admins = {u.strip().lower() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()}
        if clean_name in env_admins or clean_id in env_admins:
            return True

        return False

    def check_requester_rate_limit(self) -> Tuple[bool, int]:
        """Check if this requester has exceeded the 3 daily unlock requests limit (admins are exempt)."""
        if self.is_admin():
            return False, 0
        return check_rate_limit(self.requester_name, max_attempts=3, window_minutes=1440)


    def is_authorized_to_unlock(self, target_account_name: str) -> bool:
        """
        Authorization Policy:
        - Cross-account / Shared PC unlock is allowed so employees whose PC or phone is locked
          can use the bot service from a colleague's PC.
        - Identity verification is enforced via Two-Factor Authentication (2FA) on the employee's phone.
        """
        return True

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
        return MENU_MESSAGE, create_menu_card(
            requester_name=self.requester_name,
            requester_email=self.requester_email or self.requester_upn,
        )

    def reset(self):
        self.state = ConversationState.WAITING_FOR_TRIGGER
        self.user_data = None
        self.is_assisting_colleague = False

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
            if action == "unlock_self":
                self.is_assisting_colleague = False
                return self.handle_self_unlock()

            if action == "unlock_colleague":
                self.state = ConversationState.WAITING_FOR_NAME
                self.is_assisting_colleague = True
                return ENTER_COLLEAGUE_NAME_MESSAGE, None

            if action == "unlock_account":
                self.state = ConversationState.WAITING_FOR_NAME
                self.is_assisting_colleague = False
                return ENTER_FULL_NAME_MESSAGE, None

            if action == "confirm_unlock" and self.user_data:
                return self.prompt_or_execute_unlock()

            if action == "submit_2fa":
                code = data.get("two_factor_code") or (text or "").strip()
                return self.handle_2fa_verification(code)

            if action == "resend_2fa" and self.user_data:
                return self.resend_2fa()

            if action in ("toggle_2fa_on", "toggle_2fa_off"):
                if not self.is_admin():
                    return "⛔ **Access Denied:** Only authorized IT Administrators can modify 2FA security policies.", None
                new_state = (action == "toggle_2fa_on")
                set_2fa_enabled(new_state)
                msg = TWO_FACTOR_TOGGLE_ON_MESSAGE if new_state else TWO_FACTOR_TOGGLE_OFF_MESSAGE
                return msg, create_2fa_toggle_card(new_state, self.requester_name)

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

            if action == "setup_2fa":
                if self.user_data:
                    emp_id = self.user_data["employee_id"]
                    emp_name = self.user_data["name"]
                else:
                    found = find_user_by_name(self.requester_name) or find_user(self.requester_name)
                    if found:
                        emp_id = found["employee_id"]
                        emp_name = found["name"]
                    else:
                        emp_id = self.requester_name.strip()
                        emp_name = self.requester_name.strip()

                secret = get_totp_secret(emp_id)
                qr_url = get_totp_qr_url(emp_id, emp_name)
                msg = f"📱 **Microsoft Authenticator Setup for {emp_name}:**\nAccount: `First Assurance ({emp_id})`\nSecret Key: `{secret}`\nScan QR: {qr_url}"
                return msg, create_totp_setup_card(emp_name, emp_id, secret, qr_url)

            if action in ("restart", "reset"):
                return self.start_with_card()

        # Handle text input
        raw_text = (text or "").strip()
        text_lower = raw_text.lower()

        if not raw_text:
            if self.state == ConversationState.WAITING_FOR_TRIGGER:
                return TRIGGER_PROMPT, None
            return "Please provide an input.", None

        # Authenticator setup commands (customized for the active employee)
        if text_lower in ("setup 2fa", "2fa setup", "totp setup", "authenticator", "qr code", "2fa secret", "authenticator setup"):
            if self.user_data:
                emp_id = self.user_data["employee_id"]
                emp_name = self.user_data["name"]
            else:
                found = find_user_by_name(self.requester_name) or find_user(self.requester_name)
                if found:
                    emp_id = found["employee_id"]
                    emp_name = found["name"]
                else:
                    emp_id = self.requester_name.strip()
                    emp_name = self.requester_name.strip()

            secret = get_totp_secret(emp_id)
            qr_url = get_totp_qr_url(emp_id, emp_name)
            msg = (
                f"📱 **Microsoft Authenticator Setup for {emp_name}:**\n\n"
                f"1. Open **Microsoft Authenticator** on your phone.\n"
                f"2. Tap **+** (Add Account) ➔ Choose **Other (Google, Facebook, etc.)**.\n"
                f"3. Tap **Enter code manually** (or scan the QR code link).\n"
                f"4. **Account Name:** `First Assurance ({emp_id})`\n"
                f"5. **Secret Key:** `{secret}`\n\n"
                f"QR Code Link: {qr_url}"
            )
            return msg, create_totp_setup_card(emp_name, emp_id, secret, qr_url)

        # Admin 2FA setting commands (Strictly verified)
        if text_lower in ("2fa on", "enable 2fa", "turn on 2fa"):
            if not self.is_admin():
                return "⛔ **Access Denied:** Only authorized IT Administrators can modify 2FA security policies.", None
            set_2fa_enabled(True)
            return TWO_FACTOR_TOGGLE_ON_MESSAGE, create_2fa_toggle_card(True, self.requester_name)

        if text_lower in ("2fa off", "disable 2fa", "turn off 2fa"):
            if not self.is_admin():
                return "⛔ **Access Denied:** Only authorized IT Administrators can modify 2FA security policies.", None
            set_2fa_enabled(False)
            return TWO_FACTOR_TOGGLE_OFF_MESSAGE, create_2fa_toggle_card(False, self.requester_name)

        if text_lower in ("2fa status", "2fa", "check 2fa"):
            if not self.is_admin():
                return "⛔ **Access Denied:** Only authorized IT Administrators can view 2FA administrative controls.", None
            status_msg = TWO_FACTOR_TOGGLE_ON_MESSAGE if is_2fa_enabled() else TWO_FACTOR_TOGGLE_OFF_MESSAGE
            return status_msg, create_2fa_toggle_card(is_2fa_enabled(), self.requester_name)

        if (text_lower.startswith("2fa secret ") or text_lower.startswith("2fa set secret ")):
            if not self.is_admin():
                return "⛔ **Access Denied:** Only authorized IT Administrators can update Secret Keys.", None
            new_sec = raw_text.split()[-1]
            emp_id = self.user_data["employee_id"] if self.user_data else "nkibe"
            if set_totp_secret(emp_id, new_sec):
                return f"✅ Microsoft Authenticator Secret Key updated for `{emp_id}` to `{new_sec.upper()}`.", None
            return "❌ Invalid Base32 secret key. Allowed characters: A-Z and 2-7.", None

        # Lock / Re-lock commands (Strictly restricted to administrators for testing)
        if text_lower in ("lock me", "relock me") or text_lower.startswith("lock ") or text_lower.startswith("relock "):
            if not self.is_admin():
                return "⛔ **Access Denied:** Manual account locking is a restricted test feature for IT administrators.", None
            from backend.services.ad_service import lock_account
            target = "nkibe"
            if text_lower in ("lock me", "relock me"):
                target = "nkibe" if "kibe" in self.requester_name.lower() else self.requester_name.strip().lower()
            else:
                parts = raw_text.split()
                if len(parts) >= 2:
                    target = parts[1].strip().lower()
            lock_account(target)
            self.reset()
            return f"🔒 Account (`{target}`) has been marked as **Locked** for testing.\n\nType **Hello Bot** or **1** to test unlocking!", None

        if text_lower in ("lock all", "demo reset"):
            if not self.is_admin():
                return "⛔ **Access Denied:** Only administrators can perform a demo reset.", None
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
            if text_lower in ("2", "unlock colleague", "colleague", "for a colleague", "assist colleague", "unlock for a colleague"):
                self.state = ConversationState.WAITING_FOR_NAME
                self.is_assisting_colleague = True
                return ENTER_COLLEAGUE_NAME_MESSAGE, None
            if text_lower in MENU_UNLOCK_OPTIONS:
                return self.handle_self_unlock()
            return INVALID_MENU_MESSAGE, create_menu_card(
                requester_name=self.requester_name,
                requester_email=self.requester_email or self.requester_upn,
            )

        if self.state == ConversationState.WAITING_FOR_NAME:
            return self.handle_name_verification(raw_text)

        if self.state == ConversationState.WAITING_FOR_CONFIRMATION:
            return self.handle_confirmation(text_lower)

        if self.state == ConversationState.WAITING_FOR_2FA:
            if text_lower in ("cancel", "stop", "exit", "quit"):
                self.state = ConversationState.COMPLETED
                return CANCEL_MESSAGE, None
            if text_lower in ("resend", "resend code", "resend 2fa"):
                return self.resend_2fa()
            return self.handle_2fa_verification(raw_text)

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
                details=f"Account query failed for '{name_raw}'." if not self.is_assisting_colleague else f"Colleague query failed for '{name_raw}'.",
            )
            is_limited, attempts = self.check_requester_rate_limit()
            if is_limited:
                self.state = ConversationState.LOCKED_OUT
                return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.requester_name, attempts)

            remaining = max(0, 3 - attempts)
            fail_msg = COLLEAGUE_VERIFY_FAILED_MESSAGE if self.is_assisting_colleague else VERIFY_FAILED_MESSAGE
            return (
                f"{fail_msg}\n\n*(Daily unlock requests remaining: {remaining}/3)*",
                None,
            )

        # 2. Check daily rate limit for target employee account
        is_limited, attempts = check_rate_limit(user["employee_id"], max_attempts=3, window_minutes=1440)
        req_lower = self.requester_name.strip().lower()
        if is_limited and not any(admin in req_lower for admin in ADMIN_USERS):
            self.state = ConversationState.LOCKED_OUT
            return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(user["name"], attempts)

        # 2b. Check if user typed their own name while in colleague mode
        if self.is_assisting_colleague:
            from backend.services.entra_service import EntraService
            if EntraService.is_self_request(
                requester_name=self.requester_name,
                requester_email=self.requester_email,
                requester_upn=self.requester_upn,
                target_account=user,
            ):
                self.is_assisting_colleague = False

        # 2c. Enforce Single Colleague Policy: An employee can only open for ONE colleague per day (up to 3 times)
        colleague_unlock_count = 0
        if self.is_assisting_colleague and not self.is_admin():
            can_assist, reason, count, sponsored_name = check_colleague_sponsorship_limit(
                requester_name=self.requester_name,
                target_name=user["name"],
                target_id=user.get("employee_id"),
                max_unlocks_per_colleague=3,
                window_minutes=1440,
            )
            colleague_unlock_count = count
            if not can_assist:
                self.state = ConversationState.LOCKED_OUT
                if reason == "DIFFERENT_COLLEAGUE":
                    log_audit_event(
                        action="COLLEAGUE_POLICY_VIOLATION",
                        requester_name=self.requester_name,
                        requester_id=self.requester_id,
                        target_account_id=user.get("employee_id"),
                        target_account_name=user["name"],
                        target_department=user.get("department"),
                        status="BLOCKED",
                        details=f"Requester already unlocked for colleague '{sponsored_name}' today. Blocked from assisting multiple employees ('{user['name']}').",
                    )
                    reply = COLLEAGUE_MULTIPLE_EMPLOYEES_BLOCKED_MESSAGE.format(
                        sponsored_colleague=sponsored_name,
                        target_colleague=user["name"],
                    )
                    card = create_it_referral_card(
                        user["name"],
                        attempts=count,
                        reason="Single Colleague Policy",
                        details_text=f"Under corporate security policy, employees may only assist 1 colleague per day (up to 3 times). You have already assisted {sponsored_name} today.",
                    )
                    return reply, card
                elif reason == "COLLEAGUE_LIMIT_REACHED":
                    log_audit_event(
                        action="COLLEAGUE_LIMIT_EXCEEDED",
                        requester_name=self.requester_name,
                        requester_id=self.requester_id,
                        target_account_id=user.get("employee_id"),
                        target_account_name=user["name"],
                        target_department=user.get("department"),
                        status="BLOCKED",
                        details=f"Requester reached maximum 3 daily unlocks for colleague '{sponsored_name}'.",
                    )
                    reply = COLLEAGUE_DAILY_LIMIT_EXCEEDED_MESSAGE.format(
                        sponsored_colleague=sponsored_name,
                    )
                    card = create_it_referral_card(
                        user["name"],
                        attempts=3,
                        reason="Colleague Limit Reached (3/3)",
                        details_text=f"Maximum 3 unlocks for colleague {sponsored_name} reached today.",
                    )
                    return reply, card

        self.user_data = user

        # 3. Log verified account lookup (record both target employee and requesting user for shared PC usage)
        log_audit_event(
            action="ACCOUNT_VERIFIED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=user["employee_id"],
            target_account_name=user["name"],
            target_department=user["department"],
            status="SUCCESS",
            details=f"Account lookup for '{user['name']}' via session of '{self.requester_name}'.",
        )

        # 4. Check account status in Active Directory
        current = find_user(user["employee_id"])
        if current and current.get("locked"):
            self.state = ConversationState.WAITING_FOR_CONFIRMATION
            card = create_verification_card(
                user["name"],
                user["department"],
                status="Locked 🔒",
                is_colleague_assist=self.is_assisting_colleague,
                sponsor_name=self.requester_name if self.is_assisting_colleague else None,
                colleague_unlock_count=colleague_unlock_count,
            )
            if self.is_assisting_colleague:
                rem = max(0, 3 - colleague_unlock_count)
                text_reply = (
                    f"Colleague Identity Verified ✅\n"
                    f"Colleague: {user['name']}\n"
                    f"Department: {user['department']}\n"
                    f"Status: Locked 🔒\n"
                    f"*(Colleague unlock requests remaining today: {rem}/3)*\n\n"
                    f"Would you like to unlock this account on their behalf?"
                )
            else:
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
            if self.is_assisting_colleague:
                text_reply = f"Identity verified for colleague {user['name']}.\n\nTheir account is currently Already Unlocked 🟢. No changes were made."
            else:
                text_reply = VERIFY_SUCCESS_ALREADY_UNLOCKED_TEMPLATE.format(
                    name=user["name"],
                    department=user["department"]
                )
            return text_reply, card

    def handle_self_unlock(self) -> Tuple[str, Optional[Any]]:
        """Automatically identify and verify the requesting Entra ID user in Active Directory."""
        from backend.services.entra_service import EntraService

        # 1. Match by UPN username prefix (e.g. nkibe@firstassurance.co.ke -> nkibe)
        candidate = EntraService.map_entra_user_to_ad_username(
            upn=self.requester_upn,
            email=self.requester_email,
            display_name=self.requester_name,
        )
        user = None
        if candidate:
            user = find_user(candidate)

        # 2. Match by full display name
        if not user and self.requester_name and self.requester_name.lower() != "unknown":
            user = find_user_by_name(self.requester_name) or find_user(self.requester_name)

        # 3. Fallback to manual entry if Entra identity is not linked
        if not user:
            self.state = ConversationState.WAITING_FOR_NAME
            return "Could not automatically match your Entra ID login to an Active Directory account.\n\nPlease enter your employee ID or full name:", None

        # Check rate limit
        is_limited, attempts = check_rate_limit(user["employee_id"], max_attempts=3, window_minutes=1440)
        req_lower = self.requester_name.strip().lower()
        if is_limited and not any(admin in req_lower for admin in ADMIN_USERS):
            self.state = ConversationState.LOCKED_OUT
            return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(user["name"], attempts)

        self.user_data = user

        log_audit_event(
            action="ENTRA_SELF_VERIFIED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=user["employee_id"],
            target_account_name=user["name"],
            target_department=user["department"],
            status="SUCCESS",
            details=f"Entra ID 1-click lookup for '{user['name']}' (UPN: {self.requester_upn or 'N/A'}).",
        )

        current = find_user(user["employee_id"])
        if current and current.get("locked"):
            self.state = ConversationState.WAITING_FOR_CONFIRMATION
            card = create_verification_card(
                user["name"],
                user["department"],
                status="Locked 🔒",
                is_entra_verified=True,
            )
            text_reply = f"Hello {user['name']}! We verified your identity via Microsoft Entra ID.\n\nYour account is currently **Locked 🔒**. Click below to unlock immediately:"
            return text_reply, card
        else:
            self.state = ConversationState.COMPLETED
            card = create_already_unlocked_card(
                user["name"],
                user["department"],
            )
            text_reply = f"Hello {user['name']}! Your account is currently **Active & Unlocked 🟢**. No action is needed."
            return text_reply, card

    def prompt_or_execute_unlock(self) -> Tuple[str, Any]:
        """
        Proceed to unlock.
        If Entra ID already verified this employee for their own account,
        2FA is safely bypassed (Zero-Trust Entra Verified).
        If unlocking on behalf of a colleague and 2FA is enabled, prompt for 2FA.
        """
        from backend.services.entra_service import EntraService

        is_self = EntraService.is_self_request(
            requester_name=self.requester_name,
            requester_email=self.requester_email,
            requester_upn=self.requester_upn,
            target_account=self.user_data,
        )

        if is_self:
            logger.info("Entra ID verified self-unlock for '%s'. Bypassing manual 2FA.", self.user_data.get("name"))
            return self.execute_unlock()

        if not is_2fa_enabled():
            return self.execute_unlock()

        emp_id = self.user_data["employee_id"]
        otp = generate_otp(emp_id)
        self.state = ConversationState.WAITING_FOR_2FA
        phone_hint = mask_phone_number(self.user_data.get("phone"))
        reply = ENTER_2FA_CODE_MESSAGE.format(phone_hint=phone_hint)
        card = create_2fa_card(
            name=self.user_data["name"],
            department=self.user_data["department"],
            phone_hint=phone_hint,
            test_otp_hint=otp,
        )
        return reply, card

    def handle_2fa_verification(self, code: str) -> Tuple[str, Any]:
        """Verify the 6-digit OTP code before executing unlock."""
        if not self.user_data:
            return self.start_with_card()

        emp_id = self.user_data["employee_id"]
        success, msg = verify_otp(emp_id, code)

        if success:
            log_audit_event(
                action="2FA_VERIFICATION_SUCCESS",
                requester_name=self.requester_name,
                requester_id=self.requester_id,
                target_account_id=emp_id,
                target_account_name=self.user_data["name"],
                target_department=self.user_data["department"],
                status="SUCCESS",
                details="Identity verified successfully via Two-Factor Authentication.",
            )
            return self.execute_unlock()

        # Handle incorrect code or max attempts
        phone_hint = mask_phone_number(self.user_data.get("phone"))
        if "Maximum" in msg:
            self.state = ConversationState.LOCKED_OUT
            log_audit_event(
                action="2FA_VERIFICATION_EXCEEDED",
                requester_name=self.requester_name,
                requester_id=self.requester_id,
                target_account_id=emp_id,
                target_account_name=self.user_data["name"],
                target_department=self.user_data["department"],
                status="BLOCKED",
                details=msg,
            )
            return RATE_LIMIT_EXCEEDED_MESSAGE, create_it_referral_card(self.user_data["name"], 3)

        log_audit_event(
            action="2FA_VERIFICATION_FAILED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=emp_id,
            target_account_name=self.user_data["name"],
            target_department=self.user_data["department"],
            status="FAILURE",
            details=msg,
        )
        active_otp = get_active_otp(emp_id)
        card = create_2fa_card(
            name=self.user_data["name"],
            department=self.user_data["department"],
            phone_hint=phone_hint,
            error_message=msg,
            test_otp_hint=active_otp,
        )
        return msg, card

    def resend_2fa(self) -> Tuple[str, Any]:
        """Generate and dispatch a fresh 2FA code to the employee's phone."""
        if not self.user_data:
            return self.start_with_card()

        emp_id = self.user_data["employee_id"]
        otp = generate_otp(emp_id)
        phone_hint = mask_phone_number(self.user_data.get("phone"))
        msg = f"🔄 A new verification code has been dispatched to {phone_hint}.\n\nPlease enter the 6-digit code:"
        card = create_2fa_card(
            name=self.user_data["name"],
            department=self.user_data["department"],
            phone_hint=phone_hint,
            test_otp_hint=otp,
        )
        return msg, card

    def execute_unlock(self) -> Tuple[str, Any]:
        """Perform unlock in Active Directory, write to audit log, and return success card."""
        emp_id = self.user_data["employee_id"]

        # Final safety check on colleague sponsorship policy before unlock execution
        if self.is_assisting_colleague and not self.is_admin():
            can_assist, reason, count, sponsored_name = check_colleague_sponsorship_limit(
                requester_name=self.requester_name,
                target_name=self.user_data["name"],
                target_id=emp_id,
                max_unlocks_per_colleague=3,
                window_minutes=1440,
            )
            if not can_assist:
                self.state = ConversationState.LOCKED_OUT
                if reason == "DIFFERENT_COLLEAGUE":
                    reply = COLLEAGUE_MULTIPLE_EMPLOYEES_BLOCKED_MESSAGE.format(
                        sponsored_colleague=sponsored_name,
                        target_colleague=self.user_data["name"],
                    )
                    card = create_it_referral_card(
                        self.user_data["name"],
                        attempts=count,
                        reason="Single Colleague Policy",
                        details_text=f"Under corporate security policy, employees may only assist 1 colleague per day (up to 3 times). You have already assisted {sponsored_name} today.",
                    )
                    return reply, card
                else:
                    reply = COLLEAGUE_DAILY_LIMIT_EXCEEDED_MESSAGE.format(
                        sponsored_colleague=sponsored_name,
                    )
                    card = create_it_referral_card(
                        self.user_data["name"],
                        attempts=3,
                        reason="Colleague Limit Reached (3/3)",
                        details_text=f"Maximum 3 unlocks for colleague {sponsored_name} reached today.",
                    )
                    return reply, card

        res = unlock_account(emp_id)

        colleague_flag = " [Colleague Unlock]" if self.is_assisting_colleague else ""
        log_audit_event(
            action="UNLOCK_SUCCESS" if res.get("success") else "UNLOCK_FAILED",
            requester_name=self.requester_name,
            requester_id=self.requester_id,
            target_account_id=emp_id,
            target_account_name=self.user_data["name"],
            target_department=self.user_data["department"],
            status="SUCCESS" if res.get("success") else "FAILURE",
            details=f"Account unlock executed for '{self.user_data['name']}' requested via session of '{self.requester_name}'{colleague_flag}. 2FA required: {is_2fa_enabled()}.",
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
                return self.prompt_or_execute_unlock()

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