import logging
import os
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("entra-service")


class EntraService:
    """
    Microsoft Entra ID (Azure Active Directory) Integration Service.
    Authenticates via client credentials and interfaces with Microsoft Graph API
    to validate employee identities, check directory profiles, and enable
    Zero-Trust 1-click self-service unlocks.
    """

    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID", "").strip()
        self.client_secret = os.getenv("CLIENT_SECRET", "").strip()
        self.tenant_id = os.getenv("TENANT_ID", "").strip()
        self._cached_token: Optional[str] = None

    def is_configured(self) -> bool:
        """Return True if Entra credentials are set in environment."""
        return bool(self.client_id and self.client_secret and self.tenant_id)

    def get_access_token(self) -> Optional[str]:
        """Acquire an OAuth2 access token for Microsoft Graph API."""
        if not self.is_configured():
            logger.warning("Entra ID credentials not fully configured.")
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(token_url, data=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    self._cached_token = data.get("access_token")
                    return self._cached_token
                else:
                    logger.error("Failed to acquire Entra token: HTTP %s - %s", resp.status_code, resp.text)
                    return None
        except Exception as e:
            logger.error("Exception acquiring Entra token: %s", e)
            return None

    def get_user_profile(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Query Microsoft Graph API for employee details by UPN or Entra Object ID.
        Requires User.Read.All application permission with Admin Consent in Entra ID.
        """
        token = self.get_access_token()
        if not token:
            return None

        url = f"https://graph.microsoft.com/v1.0/users/{user_identifier}"
        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }
        params = {
            "$select": "id,displayName,mail,userPrincipalName,department,jobTitle,accountEnabled,onPremisesSamAccountName,mobilePhone"
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 403:
                    logger.warning(
                        "Graph API User.Read.All permission not yet consented. Using Teams activity claims."
                    )
                    return None
                else:
                    logger.debug("Graph API user query returned status %s for '%s'", resp.status_code, user_identifier)
                    return None
        except Exception as e:
            logger.warning("Error querying Microsoft Graph API for '%s': %s", user_identifier, e)
            return None

    @staticmethod
    def map_entra_user_to_ad_username(
        upn: Optional[str] = None,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract the Active Directory sAMAccountName from Entra ID attributes.
        In First Assurance hybrid environments:
          e.g. nkibe@firstassurance.co.ke -> nkibe
          e.g. newton.kibe@firstassurance.co.ke -> nkibe (fallback via name/AD query)
        """
        candidate = upn or email
        if candidate and "@" in candidate:
            username_prefix = candidate.split("@")[0].strip().lower()
            return username_prefix
        return None

    @staticmethod
    def is_self_request(
        requester_name: str,
        requester_email: Optional[str],
        requester_upn: Optional[str],
        target_account: Dict[str, Any],
    ) -> bool:
        """
        Verify if the requesting Teams/Entra user is unlocking their own account.
        Matches against target employee name, employee_id, and email.
        """
        req_name = (requester_name or "").strip().lower()
        target_name = (target_account.get("name") or "").strip().lower()
        target_emp_id = (target_account.get("employee_id") or "").strip().lower()
        target_email = (target_account.get("email") or "").strip().lower()

        # 1. Direct name match (or contains name)
        if req_name and target_name:
            if req_name == target_name or req_name in target_name or target_name in req_name:
                return True

        # 2. Email / UPN match
        req_email = (requester_email or "").strip().lower()
        req_upn = (requester_upn or "").strip().lower()
        if target_email and (target_email == req_email or target_email == req_upn):
            return True

        # 3. Username prefix match (e.g. nkibe@firstassurance.co.ke -> target nkibe)
        for check in (req_upn, req_email):
            if check and "@" in check:
                prefix = check.split("@")[0].strip().lower()
                if prefix == target_emp_id:
                    return True

        return False


# Global singleton instance
entra_service = EntraService()
