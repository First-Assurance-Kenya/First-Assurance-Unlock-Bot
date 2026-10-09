import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import ldap3

logger = logging.getLogger("account-unlock-real-ad")


def _guard_mock_mode():
    """Safety guard: refuse to execute if in MOCK mode."""
    data_source = os.getenv("DATA_SOURCE", "mock").strip().lower()
    if data_source == "mock":
        raise PermissionError("Real AD access is disabled in MOCK mode.")


def _is_locked_value(lockout_val) -> bool:
    if not lockout_val:
        return False
    try:
        return int(lockout_val) > 0
    except (ValueError, TypeError):
        return bool(str(lockout_val).strip() not in ("0", ""))


class RealActiveDirectoryService:
    """
    Production Active Directory LDAP Service.
    Completely isolated behind an explicit DATA_SOURCE=real check.
    Refuses to connect if DATA_SOURCE is 'mock' or unset.
    """

    def __init__(self):
        _guard_mock_mode()
        self.server_uri = os.getenv("AD_LDAP_SERVER", "")
        self.domain = os.getenv("AD_DOMAIN", "")
        self.base_dn = os.getenv("AD_BASE_DN", "")
        self.bind_user = os.getenv("AD_BIND_USER", "").strip()
        self.bind_password = os.getenv("AD_BIND_PASSWORD", "").strip()

    def get_connection(self) -> Optional[ldap3.Connection]:
        _guard_mock_mode()
        if not (self.server_uri and self.bind_user and self.bind_password):
            logger.warning("Active Directory credentials or server URI missing.")
            return None

        if "\\" not in self.bind_user and "@" not in self.bind_user and self.domain:
            full_bind_user = f"{self.domain}\\{self.bind_user}"
        else:
            full_bind_user = self.bind_user

        try:
            server = ldap3.Server(self.server_uri, get_info=ldap3.NONE, connect_timeout=5)
            for auth_type in (ldap3.SIMPLE, ldap3.NTLM):
                try:
                    bind_name = full_bind_user
                    if auth_type == ldap3.NTLM:
                        username_only = self.bind_user.split("@")[0].split("\\")[-1]
                        bind_name = f"{self.domain}\\{username_only}"

                    conn = ldap3.Connection(
                        server,
                        user=bind_name,
                        password=self.bind_password,
                        authentication=auth_type,
                        auto_bind=False,
                    )
                    if conn.bind():
                        return conn
                except Exception:
                    continue
        except Exception as e:
            logger.error("Could not connect to Active Directory: %s", e)

        return None

    def find_user(self, username: str) -> Optional[Dict[str, Any]]:
        _guard_mock_mode()
        if not username:
            return None

        conn = self.get_connection()
        if not conn:
            return None

        try:
            search_filter = f"(&(objectClass=user)(!(objectClass=computer))(sAMAccountName={username}))"
            attributes = [
                "distinguishedName",
                "sAMAccountName",
                "displayName",
                "cn",
                "mail",
                "department",
                "lockoutTime",
            ]
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=attributes,
                size_limit=1,
            )
            if conn.entries:
                entry = conn.entries[0]
                lockout_val = entry.lockoutTime.value if "lockoutTime" in entry else 0
                is_locked = _is_locked_value(lockout_val)
                disp_name = str(entry.displayName.value or entry.cn.value or username)
                dept = (
                    str(entry.department.value)
                    if "department" in entry and entry.department.value
                    else "General"
                )
                email = str(entry.mail.value) if "mail" in entry and entry.mail.value else ""
                dn = str(entry.distinguishedName.value)

                return {
                    "employee_id": str(entry.sAMAccountName.value),
                    "name": disp_name,
                    "email": email,
                    "department": dept,
                    "locked": is_locked,
                    "dn": dn,
                    "failed_attempts": 5 if is_locked else 0,
                    "is_live": True,
                }
        finally:
            conn.unbind()

        return None

    def find_user_by_name(self, full_name: str) -> Optional[Dict[str, Any]]:
        _guard_mock_mode()
        if not full_name:
            return None

        cleaned_name = full_name.strip()
        conn = self.get_connection()
        if not conn:
            return None

        try:
            search_filter = (
                f"(&(objectClass=user)(!(objectClass=computer))"
                f"(|(displayName={cleaned_name})(cn={cleaned_name})))"
            )
            attributes = [
                "distinguishedName",
                "sAMAccountName",
                "displayName",
                "cn",
                "mail",
                "department",
                "lockoutTime",
            ]
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=attributes,
                size_limit=1,
            )
            if conn.entries:
                entry = conn.entries[0]
                lockout_val = entry.lockoutTime.value if "lockoutTime" in entry else 0
                is_locked = _is_locked_value(lockout_val)
                disp_name = str(entry.displayName.value or entry.cn.value or cleaned_name)
                username = str(entry.sAMAccountName.value)
                dept = (
                    str(entry.department.value)
                    if "department" in entry and entry.department.value
                    else "General"
                )
                email = str(entry.mail.value) if "mail" in entry and entry.mail.value else ""
                dn = str(entry.distinguishedName.value)

                return {
                    "employee_id": username,
                    "name": disp_name,
                    "email": email,
                    "department": dept,
                    "locked": is_locked,
                    "dn": dn,
                    "failed_attempts": 5 if is_locked else 0,
                    "is_live": True,
                }
        finally:
            conn.unbind()

        return None

    def unlock_account(self, username: str) -> Dict[str, Any]:
        _guard_mock_mode()
        conn = self.get_connection()
        if not conn:
            return {
                "success": False,
                "message": "Cannot connect to Active Directory.",
                "status": "failed",
            }

        try:
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                attributes=["distinguishedName", "lockoutTime"],
            )
            if not conn.entries:
                return {
                    "success": False,
                    "message": "User not found in Active Directory.",
                    "status": "not_found",
                }

            entry = conn.entries[0]
            user_dn = str(entry.distinguishedName.value)
            lockout_val = entry.lockoutTime.value if "lockoutTime" in entry else 0

            if not lockout_val or lockout_val == 0:
                return {
                    "success": True,
                    "message": "Account is already unlocked.",
                    "status": "already_unlocked",
                }

            conn.modify(
                user_dn,
                {"lockoutTime": [(ldap3.MODIFY_REPLACE, [0])]}
            )

            if conn.result.get("result") == 0:
                return {
                    "success": True,
                    "message": "Account successfully unlocked in Active Directory.",
                    "status": "unlocked",
                    "unlocked_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "success": False,
                    "message": f"Active Directory unlock failed: {conn.result.get('description')}",
                    "status": "failed",
                }
        finally:
            conn.unbind()
