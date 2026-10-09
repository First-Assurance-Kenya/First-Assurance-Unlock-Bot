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
    conversation_id = "local-console-session"
    print("=" * 65)
    print("  FIRST ASSURANCE IT Account Unlock Bot - Interactive Test")
    print("=" * 65)
    print(" Available Test Users in Mock Active Directory:")
    print("   * Test Employee One   | Information Technology | Locked 🔒 (EMP001)")
    print("   * Test Employee Two   | Finance                | Active 🟢 (EMP002)")
    print("   * Test Employee Three | Human Resources        | Locked 🔒 (EMP003)")
    print("   * Jane Doe            | Human Resources        | Locked 🔒")
    print("   * Alex Johnson        | Finance                | Locked 🔒")
    print("=" * 65)
    print(" Flow:")
    print("   1. Type 'Hello Bot' to get started.")
    print("   2. Type '1' or 'unlock' (or click [🔓 Unlock Account]).")
    print("   3. Enter Full Name (e.g. Jane Doe or Alex Johnson).")
    print("   4. Verify Department & Status on Adaptive Card.")
    print("   5. Type 'Yes' (or click [🔓 Yes, Unlock Account]).")
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

        reply_text, card = handle_user_input(conversation_id, text=user_input)
        print(f"\nBot:\n{reply_text}")
        if card:
            print(format_card_preview(card))
        print()


if __name__ == "__main__":
    main()
