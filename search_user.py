import getpass
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

from backend.database.audit_db import log_audit_event
from backend.services.ad_service import (
    find_user,
    find_user_by_name,
    is_mock_mode,
    mock_users,
    search_users,
    unlock_account,
)


def update_env_password(user: str, password: str) -> bool:
    """Save the authenticated password to .env for the Teams bot."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return False
    try:
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines = []
        user_updated = False
        pass_updated = False

        for line in lines:
            if line.startswith("AD_BIND_USER="):
                new_lines.append(f"AD_BIND_USER={user}")
                user_updated = True
            elif line.startswith("AD_BIND_PASSWORD="):
                new_lines.append(f"AD_BIND_PASSWORD={password}")
                pass_updated = True
            else:
                new_lines.append(line)

        if not user_updated:
            new_lines.append(f"AD_BIND_USER={user}")
        if not pass_updated:
            new_lines.append(f"AD_BIND_PASSWORD={password}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        print(f"[-] Could not update .env: {e}")
        return False


def authenticate_real_ad():
    """Prompt for AD credentials and verify bind against the Domain Controller."""
    from backend.services.real_ad_service import RealActiveDirectoryService

    server_uri = os.getenv("AD_LDAP_SERVER", "ldap://172.17.0.220:389")
    domain = os.getenv("AD_DOMAIN", "firstassurance.co.ke")
    base_dn = os.getenv("AD_BASE_DN", "DC=firstassurance,DC=co,DC=ke")

    print("\n" + "=" * 65)
    print("      Active Directory Authentication (First Assurance)")
    print("=" * 65)
    print(f"  Domain Controller : {server_uri}")
    print(f"  Corporate Domain  : {domain}")
    print(f"  Search Base DN    : {base_dn}")
    print("=" * 65)

    default_user = os.getenv("AD_BIND_USER", "nkibe").strip() or "nkibe"

    while True:
        try:
            prompt_str = f"Enter AD Username [{default_user}]: "
            input_user = input(prompt_str).strip()
            user = input_user if input_user else default_user

            password = getpass.getpass(f"Enter AD Password for '{user}': ")
            if not password:
                print("[-] Password cannot be empty.")
                continue

            print(f"[*] Verifying credentials against Domain Controller ({server_uri})...")
            os.environ["AD_BIND_USER"] = user
            os.environ["AD_BIND_PASSWORD"] = password

            service = RealActiveDirectoryService()
            conn = service.get_connection()
            if conn:
                conn.unbind()
                print(f"[✓] Authentication successful! Connected as '{user}'.")

                # Offer to save to .env
                save_env = input("\n[?] Save credentials to .env so Teams Bot can use them? (y/N): ").strip().lower()
                if save_env in ("y", "yes"):
                    if update_env_password(user, password):
                        print("[✓] Saved to .env! (The Teams Bot can now query live Active Directory)")
                else:
                    print("[*] Credentials kept in-memory for this terminal session only.")

                return user
            else:
                print("[-] Authentication failed. Invalid username or password.")
                retry = input("[?] Retry authentication? (Y/n): ").strip().lower()
                if retry in ("n", "no"):
                    return None
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return None


def display_account_card(user: dict):
    """Print a clean visual card for an account."""
    status_badge = "🔒 LOCKED OUT" if user.get("locked") else "🟢 Active (Normal)"
    print("\n" + "-" * 60)
    print(" [✓] Account Details:")
    print(f"     • Username (sAMAccountName) : {user.get('employee_id')}")
    print(f"     • Display / Full Name       : {user.get('name')}")
    print(f"     • Department                : {user.get('department')}")
    print(f"     • Email                     : {user.get('email') or 'N/A'}")
    print(f"     • Account Status            : {status_badge}")
    if user.get("dn"):
        print(f"     • Distinguished Name (DN)   : {user.get('dn')}")
    print("-" * 60)


def handle_unlock_prompt(user: dict, active_user: str):
    """Prompt user to test unlocking the account."""
    username = user.get("employee_id")
    is_locked = user.get("locked", False)

    if is_locked:
        choice = input(f"\n[!] Account '{username}' is LOCKED. Unlock in Active Directory now? (y/N): ").strip().lower()
        if choice in ("y", "yes"):
            print(f"[*] Sending unlock command for '{username}' to Domain Controller...")
            res = unlock_account(username)
            if res.get("success"):
                print(f"[✓] SUCCESS: {res.get('message')}")
                # Log audit event
                try:
                    log_audit_event(
                        action="MANUAL_CLI_UNLOCK",
                        requester_name=f"AD:{active_user}",
                        status="SUCCESS",
                        target_account_id=username,
                        target_account_name=user.get("name"),
                        target_department=user.get("department"),
                        details=res.get("message"),
                    )
                    print("[✓] Logged unlock event to audit database.")
                except Exception as e:
                    print(f"[!] Note: Audit logging error: {e}")
                user["locked"] = False
            else:
                print(f"[-] FAILED: {res.get('message')}")
    else:
        choice = input(f"\n[i] Account '{username}' is active. Test write permission (force unlock reset)? (y/N): ").strip().lower()
        if choice in ("y", "yes"):
            print(f"[*] Testing write permission (resetting lockoutTime to 0) for '{username}'...")
            res = unlock_account(username, force=True)
            if res.get("success"):
                print(f"[✓] SUCCESS: {res.get('message')}")
                try:
                    log_audit_event(
                        action="MANUAL_CLI_TEST_UNLOCK",
                        requester_name=f"AD:{active_user}",
                        status="SUCCESS",
                        target_account_id=username,
                        target_account_name=user.get("name"),
                        target_department=user.get("department"),
                        details=res.get("message"),
                    )
                    print("[✓] Logged test event to audit database.")
                except Exception as e:
                    print(f"[!] Note: Audit logging error: {e}")
            else:
                print(f"[-] FAILED: {res.get('message')}")


def run_real_mode():
    """Run interactive real Active Directory search and unlock tool."""
    # Ensure credentials are present
    active_user = os.getenv("AD_BIND_USER", "nkibe")
    if not os.getenv("AD_BIND_PASSWORD"):
        active_user = authenticate_real_ad()
        if not active_user:
            print("Exiting tool.")
            return

    print("\n" + "=" * 65)
    print("      Active Directory Live Query & Unlock Tool")
    print("=" * 65)
    print(f"  Connected as : {active_user}")
    print("  Commands     :")
    print("    • Type an Employee ID, Username, or Name to search")
    print("    • Type 'unlock <username>' to unlock directly")
    print("    • Type 'exit' or 'quit' to close")
    print("=" * 65)

    while True:
        try:
            query = input("\nAD Query > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break

        # Check for direct unlock command
        if query.lower().startswith("unlock "):
            target_username = query[7:].strip()
            if not target_username:
                print("[-] Please specify a username to unlock, e.g. 'unlock jdoe'")
                continue
            target_user = find_user(target_username) or {"employee_id": target_username, "name": target_username, "locked": True}
            handle_unlock_prompt(target_user, active_user)
            continue

        print(f"[*] Querying Active Directory for '{query}'...")
        # Try direct exact lookup first
        user = find_user(query) or find_user_by_name(query)
        if user:
            display_account_card(user)
            handle_unlock_prompt(user, active_user)
            continue

        # Try broader search
        results = search_users(query, limit=10)
        if not results:
            print(f"[-] No Active Directory account found matching '{query}'.")
            continue

        if len(results) == 1:
            display_account_card(results[0])
            handle_unlock_prompt(results[0], active_user)
        else:
            print(f"\n[✓] Found {len(results)} matching accounts:")
            for idx, r in enumerate(results, 1):
                badge = "🔒 LOCKED" if r.get("locked") else "🟢 Active"
                print(f"    [{idx}] {r.get('employee_id'):<12} - {r.get('name'):<25} ({r.get('department')}) [{badge}]")

            sel = input("\nEnter number to select account (or press Enter to skip): ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(results):
                chosen = results[int(sel) - 1]
                display_account_card(chosen)
                handle_unlock_prompt(chosen, active_user)


def run_mock_mode():
    """Run search tool using mock data."""
    print("=" * 65)
    print("      Account Search Tool [MOCK DATA ENVIRONMENT]")
    print("=" * 65)
    print("  Real Active Directory access is completely disabled.")
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
        if query.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break

        user = find_user(query) or find_user_by_name(query)
        if not user:
            print(f"[-] No mock account found matching '{query}'.")
            print("    Available Mock Accounts:")
            for u in mock_users.values():
                print(f"    • {u['employee_id']} - {u['name']} ({u['department']})")
            continue

        display_account_card(user)
        if user["locked"]:
            ans = input(f"Unlock mock account '{user['employee_id']}'? (y/N): ").strip().lower()
            if ans in ("y", "yes"):
                unlock_account(user["employee_id"])
                print(f"[✓] Mock account '{user['employee_id']}' unlocked.")


def main():
    if "--mock" in sys.argv or is_mock_mode():
        run_mock_mode()
    else:
        run_real_mode()


if __name__ == "__main__":
    main()
