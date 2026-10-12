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


_cached_auth_type = None


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
        server_uri = self.server_uri or os.getenv("AD_LDAP_SERVER", "").strip()
        domain = self.domain or os.getenv("AD_DOMAIN", "").strip()
        bind_user = self.bind_user or os.getenv("AD_BIND_USER", "").strip()
        bind_password = self.bind_password or os.getenv("AD_BIND_PASSWORD", "").strip()

        if not (server_uri and bind_user and bind_password):
            logger.warning("Active Directory credentials or server URI missing.")
            return None

        username_only = bind_user.split("@")[0].split("\\")[-1]
        ntlm_user = f"{domain}\\{username_only}" if domain else username_only
        simple_upn = f"{username_only}@{domain}" if (domain and "@" not in bind_user) else bind_user

        global _cached_auth_type
        # Order attempts based on cached success, or try NTLM then SIMPLE
        candidate_configs = [
            (ldap3.NTLM, ntlm_user, "NTLM"),
            (ldap3.SIMPLE, simple_upn, "SIMPLE-UPN"),
            (ldap3.SIMPLE, username_only, "SIMPLE-USER"),
            (ldap3.NTLM, username_only, "NTLM-USER"),
        ]

        if _cached_auth_type == ldap3.SIMPLE:
            candidate_configs.sort(key=lambda x: 0 if x[0] == ldap3.SIMPLE else 1)
        elif _cached_auth_type == ldap3.NTLM:
            candidate_configs.sort(key=lambda x: 0 if x[0] == ldap3.NTLM else 1)

        try:
            server = ldap3.Server(server_uri, get_info=ldap3.NONE, connect_timeout=3)
            for auth_type, user_str, label in candidate_configs:
                try:
                    conn = ldap3.Connection(
                        server,
                        user=user_str,
                        password=bind_password,
                        authentication=auth_type,
                        auto_bind=False,
                    )
                    if conn.bind():
                        _cached_auth_type = auth_type
                        return conn
                except Exception:
                    continue
        except Exception as e:
            logger.error("Could not connect to Active Directory server: %s", e)

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
                "telephoneNumber",
                "mobile",
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
                phone = str(getattr(entry, "mobile", None) and entry.mobile.value or getattr(entry, "telephoneNumber", None) and entry.telephoneNumber.value or "")
                dn = str(entry.distinguishedName.value)

                return {
                    "employee_id": str(entry.sAMAccountName.value),
                    "name": disp_name,
                    "email": email,
                    "department": dept,
                    "phone": phone,
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
            safe_name = (
                cleaned_name.replace("\\", "\\5c")
                .replace("*", "\\2a")
                .replace("(", "\\28")
                .replace(")", "\\29")
            )
            attributes = [
                "distinguishedName",
                "sAMAccountName",
                "displayName",
                "cn",
                "mail",
                "department",
                "lockoutTime",
                "telephoneNumber",
                "mobile",
            ]

            # 1. Try exact match first
            search_filter = (
                f"(&(objectClass=user)(!(objectClass=computer))"
                f"(|(displayName={safe_name})(cn={safe_name})))"
            )
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=attributes,
                size_limit=1,
            )

            # 2. Fall back to wildcard match if exact match not found
            if not conn.entries:
                search_filter = (
                    f"(&(objectClass=user)(!(objectClass=computer))"
                    f"(|(displayName=*{safe_name}*)(cn=*{safe_name}*)(sAMAccountName=*{safe_name}*)))"
                )
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
                phone = str(getattr(entry, "mobile", None) and entry.mobile.value or getattr(entry, "telephoneNumber", None) and entry.telephoneNumber.value or "")
                dn = str(entry.distinguishedName.value)

                return {
                    "employee_id": username,
                    "name": disp_name,
                    "email": email,
                    "department": dept,
                    "phone": phone,
                    "locked": is_locked,
                    "dn": dn,
                    "failed_attempts": 5 if is_locked else 0,
                    "is_live": True,
                }
        finally:
            conn.unbind()

        return None

    def search_users(self, query: str, limit: int = 15) -> list:
        """Search multiple users in Active Directory matching username, display name, cn, or mail."""
        _guard_mock_mode()
        if not query:
            return []

        cleaned = query.strip()
        conn = self.get_connection()
        if not conn:
            return []

        try:
            # Escape LDAP special characters
            safe_query = (
                cleaned.replace("\\", "\\5c")
                .replace("*", "\\2a")
                .replace("(", "\\28")
                .replace(")", "\\29")
                .replace("\x00", "\\00")
            )

            search_filter = (
                f"(&(objectClass=user)(!(objectClass=computer))"
                f"(|(sAMAccountName=*{safe_query}*)(displayName=*{safe_query}*)(cn=*{safe_query}*)(mail=*{safe_query}*)))"
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
                size_limit=limit,
            )

            results = []
            for entry in conn.entries:
                sam = str(entry.sAMAccountName.value) if "sAMAccountName" in entry and entry.sAMAccountName.value else ""
                if not sam:
                    continue
                lockout_val = entry.lockoutTime.value if "lockoutTime" in entry else 0
                is_locked = _is_locked_value(lockout_val)
                disp_name = str(entry.displayName.value or entry.cn.value or sam)
                dept = (
                    str(entry.department.value)
                    if "department" in entry and entry.department.value
                    else "General"
                )
                email = str(entry.mail.value) if "mail" in entry and entry.mail.value else ""
                dn = str(entry.distinguishedName.value)

                results.append({
                    "employee_id": sam,
                    "name": disp_name,
                    "email": email,
                    "department": dept,
                    "locked": is_locked,
                    "dn": dn,
                    "failed_attempts": 5 if is_locked else 0,
                    "is_live": True,
                })
            return results
        finally:
            conn.unbind()

    def unlock_account(self, username: str, force: bool = False) -> Dict[str, Any]:
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
                    "message": f"User '{username}' not found in Active Directory.",
                    "status": "not_found",
                }

            entry = conn.entries[0]
            user_dn = str(entry.distinguishedName.value)
            lockout_val = entry.lockoutTime.value if "lockoutTime" in entry else 0
            is_locked = _is_locked_value(lockout_val)

            if not is_locked and not force:
                return {
                    "success": True,
                    "message": "Account is already unlocked (lockoutTime is 0).",
                    "status": "already_unlocked",
                    "dn": user_dn,
                }

            conn.modify(
                user_dn,
                {"lockoutTime": [(ldap3.MODIFY_REPLACE, [0])]}
            )

            if conn.result.get("result") == 0:
                return {
                    "success": True,
                    "message": f"Account '{username}' successfully unlocked in Active Directory.",
                    "status": "unlocked",
                    "unlocked_at": datetime.now().isoformat(),
                    "dn": user_dn,
                }
            else:
                desc = conn.result.get("description", "Unknown error")
                msg = conn.result.get("message", "")
                return {
                    "success": False,
                    "message": f"Active Directory unlock failed: {desc} ({msg})",
                    "status": "failed",
                    "result_code": conn.result.get("result"),
                }
        finally:
            conn.unbind()
