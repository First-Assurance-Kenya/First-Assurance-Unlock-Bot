import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.services.ad_service import find_user, find_user_by_name, is_mock_mode, mock_users


def search_user_cli():
    print("=" * 65)
    print("           Account Search Tool (Local Development)")
    print("=" * 65)

    if is_mock_mode():
        print("  MODE: [MOCK DATA ENVIRONMENT]")
        print("  SAFETY: Real Active Directory access is completely disabled.")
        print("  Type 'exit' or 'quit' to close.")
        print("=" * 65)

        while True:
            try:
                query = input("\nEnter Employee ID or Name to search: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break

            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            user = find_user(query) or find_user_by_name(query)
            if not user:
                print(f"[-] No mock account found matching '{query}'.")
                print("    Available Mock Accounts:")
                for u in mock_users.values():
                    print(f"    • {u['employee_id']} - {u['name']} ({u['department']})")
                continue

            status_badge = "🔒 LOCKED" if user["locked"] else "🟢 Active"
            print(f"\n[✓] User Found:")
            print(f"    • Employee ID   : {user['employee_id']}")
            print(f"    • Full Name     : {user['name']}")
            print(f"    • Department    : {user['department']}")
            print(f"    • Email         : {user['email']}")
            print(f"    • Status        : {status_badge}")
            print(f"    • Failed Tries  : {user['failed_attempts']}")
        return

    # Real mode safety guard
    raise RuntimeError("Real AD access is disabled in MOCK mode.")


if __name__ == "__main__":
    search_user_cli()
