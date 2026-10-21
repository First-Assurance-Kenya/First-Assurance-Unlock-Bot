import re
from typing import Any, Dict, Optional, Tuple

from bot.conversation import AccountUnlockBot

sessions: dict[str, AccountUnlockBot] = {}


def strip_mentions(text: str) -> str:
    cleaned = re.sub(r"<at>.*?</at>", "", text or "", flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def get_session(
    conversation_id: str,
    requester_name: str = "Unknown",
    requester_id: str = "N/A",
    requester_email: Optional[str] = None,
    requester_upn: Optional[str] = None,
    requester_aad_id: Optional[str] = None,
) -> AccountUnlockBot:
    session = sessions.get(conversation_id)
    if session is None:
        session = AccountUnlockBot(
            requester_name=requester_name,
            requester_id=requester_id,
            requester_email=requester_email,
            requester_upn=requester_upn,
            requester_aad_id=requester_aad_id,
        )
        sessions[conversation_id] = session
    else:
        session.set_requester(
            name=requester_name,
            user_id=requester_id,
            email=requester_email,
            upn=requester_upn,
            aad_id=requester_aad_id,
        )
    return session


def handle_user_input(
    conversation_id: str,
    text: Optional[str] = None,
    value: Optional[Dict[str, Any]] = None,
    requester_name: str = "Unknown",
    requester_id: str = "N/A",
    requester_email: Optional[str] = None,
    requester_upn: Optional[str] = None,
    requester_aad_id: Optional[str] = None,
) -> Tuple[str, Optional[Any]]:
    """Route input through the session with verified requester Entra identity."""
    session = get_session(
        conversation_id,
        requester_name=requester_name,
        requester_id=requester_id,
        requester_email=requester_email,
        requester_upn=requester_upn,
        requester_aad_id=requester_aad_id,
    )
    cleaned_text = strip_mentions(text) if text else None
    return session.process_input(text=cleaned_text, data=value)


def handle_user_text(
    conversation_id: str,
    text: str,
    requester_name: str = "Unknown",
    requester_id: str = "N/A",
    requester_email: Optional[str] = None,
    requester_upn: Optional[str] = None,
    requester_aad_id: Optional[str] = None,
) -> str:
    """Route plain text message and return text response."""
    reply_text, _ = handle_user_input(
        conversation_id,
        text=text,
        requester_name=requester_name,
        requester_id=requester_id,
        requester_email=requester_email,
        requester_upn=requester_upn,
        requester_aad_id=requester_aad_id,
    )
    return reply_text
