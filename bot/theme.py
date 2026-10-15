"""
Branding and Theme configuration for First Assurance Company.
Customizable corporate colors and identity settings for Adaptive Cards and Teams manifest.
"""
import os

# Company Branding & Identity
COMPANY_NAME = "First Assurance"
COMPANY_TAGLINE = "Insure • Secure • Assure"
COMPANY_PORTAL_TITLE = "IT Account Unlock Portal"

# Corporate Color Palette:
# First Assurance Official Brand Identity:
# Primary: Signature Warm Corporate Orange (#F78723)
# Secondary Accent: Deep Amber / Warm Gold (#EA7612)
# Neutral Contrast: Crisp Pure White (#FFFFFF)
# Background / Card Surface: Warm Neutral (#FFFBF5 / #FFFFFF)
# Text / Header Contrast: Deep Slate Charcoal (#1E293B)
BRAND_PRIMARY_HEX = "#F78723"
BRAND_ORANGE_HEX = "#F78723"
BRAND_ORANGE_DARK_HEX = "#EA7612"
BRAND_WHITE_HEX = "#FFFFFF"
BRAND_CHARCOAL_HEX = "#1E293B"
BRAND_BACKGROUND_HEX = "#FFFBF5"

# Card Header Text
CARD_HEADER_TITLE = f"🛡️ {COMPANY_NAME}"
CARD_HEADER_SUBTITLE = f"{COMPANY_TAGLINE} • {COMPANY_PORTAL_TITLE}"

# Logo and Visual Asset Delivery
DEV_TUNNEL_URL = os.getenv("DEV_TUNNEL_URL", "https://vrt0glbb-3978.uks1.devtunnels.ms").rstrip("/")
LOGO_PUBLIC_URL = os.getenv(
    "LOGO_PUBLIC_URL",
    f"{DEV_TUNNEL_URL}/static/first_assurance_logo.png",
)
