from typing import Optional

from bot.theme import CARD_HEADER_SUBTITLE, CARD_HEADER_TITLE
from microsoft_teams.cards import (
    AdaptiveCard,
    Container,
    Fact,
    FactSet,
    SubmitAction,
    TextBlock,
)


def create_brand_header() -> Container:
    """Branded top banner for First Assurance company."""
    return Container(
        style="emphasis",
        bleed=True,
        items=[
            TextBlock(
                text=CARD_HEADER_TITLE,
                weight="Bolder",
                size="Medium",
                color="Accent",
            ),
            TextBlock(
                text=CARD_HEADER_SUBTITLE,
                size="Small",
                isSubtle=True,
            ),
        ],
    )


def create_menu_card() -> AdaptiveCard:
    """Card for the initial First Assurance bot menu."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="Hello! How would you like me to help you today?",
                        size="Medium",
                    )
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔓 Unlock Account",
                data={"action": "unlock_account"},
                style="positive",
            )
        ],
    )


def create_verification_card(
    name: str,
    department: str,
    status: str = "Locked 🔒"
) -> AdaptiveCard:
    """Card showing employee name verification, department, and unlock prompt."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="Identity Verified ✅",
                        weight="Bolder",
                        size="Large",
                        color="Good",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Full Name", value=name),
                            Fact(title="Department", value=department),
                            Fact(title="Account Status", value=status),
                        ]
                    ),
                    TextBlock(
                        text="Would you like me to unlock your account?",
                        weight="Bolder",
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔓 Yes, Unlock Account",
                data={"action": "confirm_unlock"},
                style="positive",
            ),
            SubmitAction(
                title="❌ Cancel",
                data={"action": "cancel"},
                style="destructive",
            ),
        ],
    )


def create_success_card(name: str, department: str) -> AdaptiveCard:
    """Card confirming successful account unlock with First Assurance branding."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="Account Unlocked 🎉",
                        weight="Bolder",
                        size="Large",
                        color="Good",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Full Name", value=name),
                            Fact(title="Department", value=department),
                            Fact(title="Account Status", value="Active / Unlocked 🟢"),
                        ]
                    ),
                    TextBlock(
                        text="Your account has been successfully unlocked. You can now try signing in again.",
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔄 Start New Request",
                data={"action": "restart"},
            )
        ],
    )


def create_already_unlocked_card(name: str, department: str) -> AdaptiveCard:
    """Card when the account is already active."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="Account Status ℹ️",
                        weight="Bolder",
                        size="Large",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Full Name", value=name),
                            Fact(title="Department", value=department),
                            Fact(title="Account Status", value="Already Unlocked 🟢"),
                        ]
                    ),
                    TextBlock(
                        text="Your account is not currently locked. No changes were made.",
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔄 Start New Request",
                data={"action": "restart"},
            )
        ],
    )


def create_it_referral_card(name: str, attempts: int = 3, reason: str = "Rate limit reached") -> AdaptiveCard:
    """Card displayed when a user exceeds maximum attempts and is referred to IT Help Desk."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="⚠️ Referred to IT Service Desk",
                        weight="Bolder",
                        size="Large",
                        color="Attention",
                    ),
                    TextBlock(
                        text=f"Security alert: {attempts} unverified or failed unlock attempts have been detected. For account safety, automated self-service is temporarily locked.",
                        wrap=True,
                        spacing="Small",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Status", value="Referred to IT Helpdesk"),
                            Fact(title="Attempts Recorded", value=f"{attempts} / 3 Maximum"),
                            Fact(title="Help Desk Email", value="ithelpdesk@firstassurance.co.ke"),
                            Fact(title="Internal Phone", value="Ext 4444 / 020 2900000"),
                            Fact(title="Support Hours", value="Mon - Fri, 8:00 AM - 5:00 PM"),
                        ]
                    ),
                    TextBlock(
                        text="An IT support engineer will verify your identity manually and assist you with resetting your credentials.",
                        isSubtle=True,
                        wrap=True,
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔄 Start Over",
                data={"action": "restart"},
            )
        ],
    )


def create_unauthorized_card(requester_name: str, target_name: str) -> AdaptiveCard:
    """Card displayed when a user attempts to unlock an account other than their own."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="🛡️ Self-Service Security Policy",
                        weight="Bolder",
                        size="Large",
                        color="Attention",
                    ),
                    TextBlock(
                        text="In accordance with IT security policies, you may only unlock your own corporate account.",
                        wrap=True,
                        spacing="Small",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Your Verified Login", value=requester_name),
                            Fact(title="Requested Account", value=target_name),
                            Fact(title="Policy Decision", value="Denied (Identity Mismatch)"),
                        ]
                    ),
                    TextBlock(
                        text="If you are experiencing issues with another employee's account, please have them contact IT Help Desk or reach out directly to ithelpdesk@firstassurance.co.ke.",
                        isSubtle=True,
                        wrap=True,
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="🔄 Start Over",
                data={"action": "restart"},
            )
        ],
    )
