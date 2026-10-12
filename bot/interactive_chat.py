import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.teams_session import handle_user_input


def format_card_preview(card) -> str:
    """Format an AdaptiveCard for display in the local console."""
    if not card:
        return ""
    lines = ["\n--- [Adaptive Card Preview] ---"]

    def process_items(elements):
        for elem in elements:
            if hasattr(elem, "text"):
                lines.append(f"  {elem.text}")
            elif hasattr(elem, "placeholder"):
                lines.append(f"  [Input Field ({getattr(elem, 'id', 'input')}): {elem.placeholder}]")
            elif hasattr(elem, "facts"):
                for fact in elem.facts:
                    lines.append(f"    • {fact.title}: {fact.value}")
            elif hasattr(elem, "items"):
                process_items(elem.items)

    if hasattr(card, "body"):
        process_items(card.body)

    if hasattr(card, "actions") and card.actions:
        button_titles = [f"[{act.title}]" for act in card.actions]
        lines.append(f"  Actions: {' '.join(button_titles)}")
    lines.append("------------------------------")
    return "\n".join(lines)


def main():
    import os
    conversation_id = "local-console-session"
    data_source = os.getenv("DATA_SOURCE", "mock").lower()
    requester = "Newton Kibe"

    print("=" * 65)
    print("  FIRST ASSURANCE IT Account Unlock Bot - Interactive Terminal Chat")
    print("=" * 65)
    if data_source == "real":
        print("  MODE: LIVE CORPORATE ACTIVE DIRECTORY")
        print("  Domain: firstassurance.co.ke | Server: 172.17.0.220:389")
        print(f"  Simulated Authenticated User: {requester}")
    else:
        print("  MODE: MOCK DATA ENVIRONMENT")
        print("  Available Test Users: Jane Doe, Alex Johnson, Test Employee One")
    print("=" * 65)
    print(" Flow:")
    print("   1. Type 'Hello Bot' to get started.")
    print("   2. Type '1' to select Unlock Account.")
    print("   3. Enter Full Name (e.g. Newton Kibe or any employee).")
    print("   4. Type 'Yes' to confirm.")
    print("   5. If 2FA is active, enter the 6-digit code from Microsoft Authenticator.")
    print("   * Useful Commands: 'setup 2fa' (show Authenticator key/QR), 'lock me', '2fa on/off'")
    print("   * Type 'exit' or 'quit' to close.")
    print("=" * 65)


    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Session ended.")
            break

        reply_text, card = handle_user_input(
            conversation_id, text=user_input, requester_name=requester
        )
        print(f"\nBot:\n{reply_text}")
        if card:
            print(format_card_preview(card))
        print()


if __name__ == "__main__":
    main()
