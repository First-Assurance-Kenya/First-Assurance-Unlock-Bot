import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import struct
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("two-factor-service")

ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT / ".env"
SECRETS_FILE = ROOT / "data" / "totp_secrets.json"

# In-memory runtime flag (defaults to True if not explicitly set to 'false')
_env_val = os.getenv("ENABLE_2FA", "true").strip().lower()
_runtime_2fa_enabled: bool = _env_val not in ("false", "0", "no", "off")

# In-memory store for active OTP codes: account_id -> {code, created_at, attempts}
_active_otps: Dict[str, Dict] = {}

OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3

# Predefined clean Base32 secrets for known test accounts (standard RFC 6238 TOTP)
DEFAULT_SECRETS: Dict[str, str] = {
    "NKIBE": "FAUNLOCKNKIBE2FA",
    "NEWTON01": "FAUNLOCKNKIBE2FA",
}


def is_2fa_enabled() -> bool:
    """Return True if 2FA verification is currently required before unlocking."""
    global _runtime_2fa_enabled
    return _runtime_2fa_enabled


def set_2fa_enabled(enabled: bool) -> bool:
    """
    Toggle 2FA requirement on/off and persist to .env.
    Can be invoked by an administrator directly in chat (e.g. '2fa on' / '2fa off').
    """
    global _runtime_2fa_enabled
    _runtime_2fa_enabled = bool(enabled)
    logger.info("2FA verification requirement set to: %s", _runtime_2fa_enabled)

    # Persist to .env file
    if ENV_PATH.exists():
        try:
            content = ENV_PATH.read_text(encoding="utf-8")
            target_line = f"ENABLE_2FA={'true' if _runtime_2fa_enabled else 'false'}"
            if "ENABLE_2FA=" in content:
                content = re.sub(r"ENABLE_2FA=.*", target_line, content)
            else:
                content += f"\nENABLE_2FA={'true' if _runtime_2fa_enabled else 'false'}\n"
            ENV_PATH.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning("Could not persist ENABLE_2FA to .env: %s", e)

    return _runtime_2fa_enabled


# =====================================================================
# Authenticator App (RFC 6238 TOTP) Support
# Compatible with Microsoft Authenticator, Google Authenticator, etc.
# =====================================================================

def get_totp_secret(account_id: str) -> str:
    """
    Retrieve or generate a persistent Base32 secret for Authenticator apps (RFC 6238).
    """
    clean_id = str(account_id).strip().upper()

    # 1. Environment variable override (e.g. TOTP_SECRET_NKIBE)
    env_key = f"TOTP_SECRET_{clean_id}"
    env_secret = os.getenv(env_key) or os.getenv("DEFAULT_TOTP_SECRET")
    if env_secret:
        return env_secret.strip().upper()

    # 2. Check JSON file storage
    if SECRETS_FILE.exists():
        try:
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
            if clean_id in data:
                return data[clean_id]
        except Exception as e:
            logger.warning("Could not read totp_secrets.json: %s", e)

    # 3. Check predefined dictionary
    if clean_id in DEFAULT_SECRETS:
        return DEFAULT_SECRETS[clean_id]

    # 4. Generate deterministic Base32 secret based on account_id
    h = hashlib.sha256(f"FA_UNLOCK_{clean_id}".encode()).digest()
    b32 = base64.b32encode(h)[:16].decode("ascii").upper()

    try:
        SECRETS_FILE.parent.mkdir(exist_ok=True)
        data = {}
        if SECRETS_FILE.exists():
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        data[clean_id] = b32
        SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not persist totp secret: %s", e)

    return b32


def set_totp_secret(account_id: str, secret_base32: str) -> bool:
    """Manually configure an employee's Authenticator secret key."""
    clean_id = str(account_id).strip().upper()
    clean_secret = re.sub(r"[^A-Za-z2-7]", "", secret_base32).upper()
    if len(clean_secret) < 8:
        return False
    try:
        base64.b32decode(clean_secret, casefold=True)
    except Exception:
        return False

    try:
        data = {}
        if SECRETS_FILE.exists():
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        data[clean_id] = clean_secret
        SECRETS_FILE.parent.mkdir(exist_ok=True)
        SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Custom TOTP secret saved for '%s'.", clean_id)
        return True
    except Exception as e:
        logger.error("Failed to save custom TOTP secret: %s", e)
        return False


def compute_totp(secret_base32: str, for_time: Optional[float] = None, time_step: int = 30) -> str:
    """Compute standard RFC 6238 6-digit TOTP code for the given Base32 secret."""
    t = time.time() if for_time is None else for_time
    counter = int(t // time_step)
    key = base64.b32decode(secret_base32.upper(), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def verify_totp_code(secret_base32: str, code: str, window: int = 1) -> bool:
    """
    Verify submitted 6-digit code against standard RFC 6238 TOTP algorithm.
    window=1 checks the current 30s window plus previous and next windows (±30s)
    to smoothly accommodate slight clock differences between phone and server.
    """
    clean_code = str(code or "").strip().replace(" ", "").replace("-", "")
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False

    try:
        key = base64.b32decode(secret_base32.upper(), casefold=True)
    except Exception:
        return False

    current_counter = int(time.time() // 30)
    for offset in range(-window, window + 1):
        msg = struct.pack(">Q", current_counter + offset)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        idx = digest[19] & 0x0F
        expected = (struct.unpack(">I", digest[idx : idx + 4])[0] & 0x7FFFFFFF) % 1000000
        if f"{expected:06d}" == clean_code:
            return True
    return False


def get_totp_uri(account_id: str, display_name: str = "User", issuer: str = "First Assurance") -> str:
    """Generate standard otpauth:// URI for Microsoft Authenticator / Google Authenticator."""
    secret = get_totp_secret(account_id)
    label = urllib.parse.quote(f"{issuer}:{account_id}")
    iss = urllib.parse.quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={iss}"


def get_totp_qr_url(account_id: str, display_name: str = "User", issuer: str = "First Assurance") -> str:
    """Generate QR code image URL for scanning directly with Microsoft Authenticator."""
    uri = get_totp_uri(account_id, display_name, issuer)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(uri)}"


# =====================================================================
# OTP Dispatch & Verification
# =====================================================================

def generate_otp(account_id: str) -> str:
    """
    Generate or retrieve verification credentials for the given account.
    Also computes the active Microsoft Authenticator TOTP code for reference.
    """
    clean_id = str(account_id).strip().upper()
    code = f"{secrets.randbelow(900000) + 100000}"

    _active_otps[clean_id] = {
        "code": code,
        "created_at": datetime.now(),
        "attempts": 0,
    }

    # Log both the live Authenticator code and the fallback OTP
    secret = get_totp_secret(clean_id)
    live_totp = compute_totp(secret)
    logger.info(
        "[2FA AUTHENTICATOR] Account '%s': Secret=%s | Live Authenticator Code=%s | Fallback OTP=%s",
        clean_id,
        secret,
        live_totp,
        code,
    )
    return code


def get_active_otp(account_id: str) -> Optional[str]:
    """Retrieve the current active fallback OTP code if not expired."""
    clean_id = str(account_id).strip().upper()
    record = _active_otps.get(clean_id)
    if not record:
        return None

    if datetime.now() - record["created_at"] > timedelta(minutes=OTP_EXPIRY_MINUTES):
        _active_otps.pop(clean_id, None)
        return None

    return record["code"]


def verify_otp(account_id: str, submitted_code: str) -> Tuple[bool, str]:
    """
    Verify 6-digit code submitted by employee.
    Supports:
    1. Real Microsoft Authenticator (RFC 6238 TOTP) rolling 30-second code from the phone.
    2. Fallback dispatched OTP code.
    """
    clean_id = str(account_id).strip().upper()
    clean_code = str(submitted_code or "").strip().replace(" ", "").replace("-", "")

    # 1. Verify against Microsoft Authenticator TOTP
    secret = get_totp_secret(clean_id)
    if verify_totp_code(secret, clean_code):
        _active_otps.pop(clean_id, None)
        logger.info("[2FA SUCCESS] Account '%s' verified via Microsoft Authenticator app.", clean_id)
        return True, "Microsoft Authenticator verification successful."

    # 2. Verify against dispatched OTP record
    record = _active_otps.get(clean_id)
    if record:
        if datetime.now() - record["created_at"] <= timedelta(minutes=OTP_EXPIRY_MINUTES):
            if clean_code == record["code"]:
                _active_otps.pop(clean_id, None)
                logger.info("[2FA SUCCESS] Account '%s' verified via dispatched OTP.", clean_id)
                return True, "Two-factor verification successful."

    # Handle incorrect code
    if record:
        record["attempts"] += 1
        remaining = MAX_OTP_ATTEMPTS - record["attempts"]
        if remaining <= 0:
            _active_otps.pop(clean_id, None)
            logger.warning("[2FA BLOCKED] Account '%s' exceeded maximum 2FA attempts.", clean_id)
            return False, "Maximum 2FA verification attempts exceeded. For security, automated self-service is locked."

        logger.warning("[2FA MISMATCH] Incorrect code for '%s'. %d attempts remaining.", clean_id, remaining)
        return False, f"Incorrect verification code. Please check your Authenticator app and try again ({remaining}/3 attempts remaining)."

    # If no active session was initiated
    return False, "Incorrect verification code. Please check your Microsoft Authenticator app or request a new code."


def mask_phone_number(phone_raw: Optional[str]) -> str:
    """Format and mask phone number for display (e.g., +254 7** *** **89)."""
    if not phone_raw:
        return "Microsoft Authenticator app / SMS"

    digits = re.sub(r"[^\d+]", "", str(phone_raw))
    if len(digits) >= 9:
        prefix = digits[:5]
        suffix = digits[-2:]
        return f"{prefix} *** *** {suffix}"
    elif len(digits) >= 6:
        return f"{digits[:2]} *** {digits[-2:]}"

    return "Microsoft Authenticator app / SMS"
