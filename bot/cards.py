from typing import Optional

from bot.theme import CARD_HEADER_SUBTITLE, CARD_HEADER_TITLE
from microsoft_teams.cards import (
    AdaptiveCard,
    Container,
    Fact,
    FactSet,
    OpenUrlAction,
    SubmitAction,
    TextBlock,
    TextInput,
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
                        text=f"Security alert: You have reached {attempts} unlock requests today. For account safety, users are limited to 3 unlock requests per day.",
                        wrap=True,
                        spacing="Small",
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Status", value="Referred to IT Helpdesk"),
                            Fact(title="Daily Requests", value=f"{attempts} / 3 Maximum per day"),
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


def create_2fa_card(
    name: str,
    department: str,
    phone_hint: str = "Microsoft Authenticator",
    error_message: Optional[str] = None,
    test_otp_hint: Optional[str] = None,
) -> AdaptiveCard:
    """Card prompting employee to enter the 6-digit 2FA code from Microsoft Authenticator."""
    items = [
        TextBlock(
            text="Two-Factor Authentication (2FA) 📱",
            weight="Bolder",
            size="Large",
            color="Accent",
        ),
        FactSet(
            facts=[
                Fact(title="Employee", value=name),
                Fact(title="Department", value=department),
                Fact(title="Verification Source", value="Microsoft Authenticator App"),
            ]
        ),
        TextBlock(
            text="Please enter the active 6-digit code from your **Microsoft Authenticator app** to confirm your identity before unlocking:",
            wrap=True,
            spacing="Medium",
        ),
    ]

    if error_message:
        items.append(
            TextBlock(
                text=error_message,
                color="Attention",
                weight="Bolder",
                wrap=True,
                spacing="Small",
            )
        )

    items.append(
        TextInput(
            id="two_factor_code",
            placeholder="Enter 6-digit code from phone (e.g. 123456)",
            maxLength=6,
        )
    )

    if test_otp_hint:
        items.append(
            TextBlock(
                text=f"*(Dispatched / Fallback Code: {test_otp_hint})*",
                isSubtle=True,
                spacing="None",
            )
        )

    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(items=items),
        ],
        actions=[
            SubmitAction(
                title="🔑 Verify & Unlock",
                data={"action": "submit_2fa"},
                style="positive",
            ),
            SubmitAction(
                title="📱 Authenticator Setup / QR",
                data={"action": "setup_2fa"},
            ),
            SubmitAction(
                title="❌ Cancel",
                data={"action": "cancel"},
                style="destructive",
            ),
        ],
    )


def create_totp_setup_card(
    name: str,
    account_id: str,
    secret: str,
    qr_url: str,
) -> AdaptiveCard:
    """Card guiding employee to pair Microsoft Authenticator with their corporate account."""
    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text="📱 Setup Microsoft Authenticator",
                        weight="Bolder",
                        size="Large",
                        color="Accent",
                    ),
                    TextBlock(
                        text=f"Pair your mobile **Microsoft Authenticator** app for **{name}** (`{account_id}`):",
                        wrap=True,
                    ),
                    FactSet(
                        facts=[
                            Fact(title="Account Name", value=f"First Assurance ({account_id})"),
                            Fact(title="Secret Key", value=secret),
                            Fact(title="Type", value="Time-based (TOTP / 30 seconds)"),
                        ]
                    ),
                    TextBlock(
                        text="**Quick Setup in Microsoft Authenticator:**\n1. Open **Microsoft Authenticator** on your phone.\n2. Tap **+** (Add Account) ➔ Choose **Other (Google, Facebook, etc.)**.\n3. Tap **Enter code manually** (or scan the QR code link below).\n4. Enter the Secret Key above and save.",
                        wrap=True,
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            OpenUrlAction(
                title="🔍 View Scanable QR Code",
                url=qr_url,
            ),
            SubmitAction(
                title="🔑 Enter 2FA Code",
                data={"action": "confirm_unlock"},
                style="positive",
            ),
            SubmitAction(
                title="🔄 Main Menu",
                data={"action": "restart"},
            ),
        ],
    )



def create_2fa_toggle_card(enabled: bool, admin_name: str) -> AdaptiveCard:
    """Card showing current 2FA setting status and toggle button for administrators."""
    status_text = "ENABLED 🔐" if enabled else "DISABLED 🔓"
    status_desc = (
        "Employees are REQUIRED to verify their identity via mobile 2FA code before unlocking accounts."
        if enabled
        else "Employees can unlock accounts with direct confirmation WITHOUT entering a 2FA code."
    )
    badge_color = "Good" if enabled else "Warning"

    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                items=[
                    TextBlock(
                        text=f"2FA Setting: {status_text}",
                        weight="Bolder",
                        size="Large",
                        color=badge_color,
                    ),
                    FactSet(
                        facts=[
                            Fact(title="2FA Requirement", value=status_text),
                            Fact(title="Managed By", value=admin_name),
                        ]
                    ),
                    TextBlock(
                        text=status_desc,
                        wrap=True,
                        spacing="Medium",
                    ),
                ]
            ),
        ],
        actions=[
            SubmitAction(
                title="Turn 2FA OFF 🔓" if enabled else "Turn 2FA ON 🔐",
                data={"action": "toggle_2fa_off" if enabled else "toggle_2fa_on"},
                style="destructive" if enabled else "positive",
            ),
            SubmitAction(
                title="🔄 Return to Menu",
                data={"action": "restart"},
            ),
        ],
    )
