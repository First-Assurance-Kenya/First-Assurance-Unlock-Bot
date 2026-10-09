TRIGGER_PROMPT = "Please type 'Hello Bot' to get started."

MENU_MESSAGE = """Hello! How would you like me to help you today?

1. 🔓 Unlock Account"""

ENTER_FULL_NAME_MESSAGE = "Please enter your full name."

VERIFY_SUCCESS_LOCKED_TEMPLATE = """Identity verified.
Name: {name}
Department: {department}
Status: Locked 🔒

Would you like me to unlock it?"""

VERIFY_SUCCESS_ALREADY_UNLOCKED_TEMPLATE = """Identity verified.
Name: {name}
Department: {department}
Status: Already Unlocked 🟢

Your account is not currently locked. No changes were made."""

VERIFY_FAILED_MESSAGE = """I couldn't find an account matching that full name.

Please check your spelling and enter your full name again (or type 'reset' to restart)."""

ACCOUNT_UNLOCKED_MESSAGE = "Your account has been successfully unlocked."

CANCEL_MESSAGE = """No changes were made to your account.

If you need assistance later, just type 'Hello Bot' to get started."""

INVALID_MENU_MESSAGE = """Please select a valid option:

1. 🔓 Unlock Account"""

INVALID_CONFIRMATION_MESSAGE = """Please respond with Yes or No (or click a button).

Would you like me to unlock your account?"""

RATE_LIMIT_EXCEEDED_MESSAGE = """⚠️ Maximum attempts exceeded (3/3).

For account security, automated self-service has been locked. Your request has been referred to the IT Service Desk:
• Email: ithelpdesk@firstassurance.co.ke
• Phone: Ext 4444 / 020 2900000
• Hours: Mon - Fri, 8:00 AM - 5:00 PM"""

UNAUTHORIZED_ACCOUNT_MESSAGE = """🛡️ Security Policy Violation:

You are authenticated as '{requester}'. Self-service account unlock is restricted to your own verified identity. You cannot unlock an account belonging to '{target}'.

If you require assistance for another user, please contact the IT Helpdesk directly."""