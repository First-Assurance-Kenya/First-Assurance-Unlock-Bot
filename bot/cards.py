from typing import Optional

from bot.theme import CARD_HEADER_SUBTITLE, CARD_HEADER_TITLE, LOGO_PUBLIC_URL
from microsoft_teams.cards import (
    AdaptiveCard,
    Container,
    Fact,
    FactSet,
    Image,
    OpenUrlAction,
    SubmitAction,
    TextBlock,
    TextInput,
)



def create_brand_header() -> Container:
    """Branded top banner for First Assurance company with official logo and corporate styling."""
    header_items = []
    if LOGO_PUBLIC_URL:
        header_items.append(
            Image(
                url=LOGO_PUBLIC_URL,
                alt_text="First Assurance - Insure • Secure • Assure",
                size="Stretch",
                horizontal_alignment="Center",
            )
        )

    header_items.append(
        TextBlock(
            text="🔒 IT Account Unlock Portal",
            weight="Bolder",
            size="Medium",
            spacing="Small",
        )
    )
    header_items.append(
        TextBlock(
            text="Insure • Secure • Assure • IT Self-Service",
            size="Small",
            isSubtle=True,
            spacing="None",
        )
    )

    return Container(
        style="emphasis",
        bleed=True,
        show_border=True,
        rounded_corners=True,
        items=header_items,
    )



def create_menu_card(
    requester_name: Optional[str] = None,
    requester_email: Optional[str] = None,
) -> AdaptiveCard:
    """Card for the initial First Assurance bot menu with Entra ID user recognition."""
    menu_items = []

    if requester_name and requester_name.strip() and requester_name.lower() != "unknown":
        menu_items.append(
            TextBlock(
                text=f"Welcome, {requester_name}! 👋",
                size="Large",
                weight="Bolder",
            )
        )
        badge_text = "🛡️ Verified Microsoft Entra ID Session"
        if requester_email:
            badge_text += f" • {requester_email}"
        menu_items.append(
            TextBlock(
                text=badge_text,
                size="Small",
                isSubtle=True,
                spacing="None",
            )
        )
        menu_items.append(
            TextBlock(
                text="Choose an option below to proceed:",
                spacing="Small",
            )
        )
        menu_items.append(
            Container(
                style="warning",
                show_border=True,
                rounded_corners=True,
                spacing="Medium",
                select_action=SubmitAction(
                    title="1. Unlock My Account",
                    data={"action": "unlock_self"},
                ),
                items=[
                    TextBlock(
                        text="🔓  1. Unlock My Account (1-Click)",
                        weight="Bolder",
                        size="Medium",
                        horizontal_alignment="Center",
                    ),
                ],
            )
        )
        card_actions = [
            SubmitAction(
                title="🔓 1. Unlock My Account",
                data={"action": "unlock_self"},
            ),
            SubmitAction(
                title="👥 Unlock for a Colleague",
                data={"action": "unlock_account"},
            ),
        ]
    else:
        menu_items.extend([
            TextBlock(
                text="Hello! How would you like me to help you today?",
                size="Medium",
                weight="Bolder",
            ),
            TextBlock(
                text="Select an option below to begin IT account self-service.",
                isSubtle=True,
                spacing="Small",
            ),
            Container(
                style="warning",
                show_border=True,
                rounded_corners=True,
                spacing="Medium",
                select_action=SubmitAction(
                    title="1. Unlock Account",
                    data={"action": "unlock_account"},
                ),
                items=[
                    TextBlock(
                        text="🔓  1. Unlock Account",
                        weight="Bolder",
                        size="Medium",
                        horizontal_alignment="Center",
                    ),
                ],
            ),
        ])
        card_actions = [
            SubmitAction(
                title="🔓 1. Unlock Account",
                data={"action": "unlock_account"},
            )
        ]

    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                show_border=True,
                rounded_corners=True,
                style="emphasis",
                items=menu_items,
            ),
        ],
        actions=card_actions,
    )



def create_verification_card(
    name: str,
    department: str,
    status: str = "Locked 🔒",
    is_entra_verified: bool = False,
) -> AdaptiveCard:
    """Card showing employee name verification, department, and unlock prompt."""
    facts = [
        Fact(title="Full Name", value=name),
        Fact(title="Department", value=department),
        Fact(title="Account Status", value=status),
    ]
    if is_entra_verified:
        facts.append(Fact(title="Authentication", value="Microsoft Entra ID (MFA Verified) 🛡️"))

    card_items = [
        TextBlock(
            text="Identity Verified ✅",
            weight="Bolder",
            size="Large",
            color="Good",
        ),
        FactSet(facts=facts),
    ]

    if is_entra_verified:
        card_items.append(
            TextBlock(
                text="✅ Identity verified via Microsoft Entra ID. No additional 2FA code is needed.",
                color="Good",
                size="Small",
                spacing="Small",
            )
        )

    card_items.extend([
        TextBlock(
            text="Would you like me to unlock your account?",
            weight="Bolder",
            spacing="Medium",
        ),
        Container(
            style="warning",
            show_border=True,
            rounded_corners=True,
            spacing="Medium",
            select_action=SubmitAction(
                title="Yes, Unlock Account",
                data={"action": "confirm_unlock"},
            ),
            items=[
                TextBlock(
                    text="🔓  Yes, Unlock Account",
                    weight="Bolder",
                    size="Medium",
                    horizontal_alignment="Center",
                ),
            ],
        ),
    ])

    return AdaptiveCard(
        body=[
            create_brand_header(),
            Container(
                show_border=True,
                rounded_corners=True,
                style="emphasis",
                items=card_items,
            ),
        ],
        actions=[
            SubmitAction(
                title="🔓 Yes, Unlock Account",
                data={"action": "confirm_unlock"},
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
                show_border=True,
                rounded_corners=True,
                style="emphasis",
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
                show_border=True,
                rounded_corners=True,
                style="emphasis",
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
            color="Warning",
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
            Container(
                show_border=True,
                rounded_corners=True,
                style="emphasis",
                items=items,
            ),
        ],
        actions=[
            SubmitAction(
                title="🔑 Verify & Unlock",
                data={"action": "submit_2fa"},
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
                show_border=True,
                rounded_corners=True,
                style="emphasis",
                items=[
                    TextBlock(
                        text="📱 Setup Microsoft Authenticator",
                        weight="Bolder",
                        size="Large",
                        color="Warning",
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
                show_border=True,
                rounded_corners=True,
                style="emphasis",
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
                style="destructive" if enabled else "default",
            ),
            SubmitAction(
                title="🔄 Return to Menu",
                data={"action": "restart"},
            ),
        ],
    )

