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


def test_ad():
    # Hard safety guard: refuse execution if in mock mode
    data_source = os.getenv("DATA_SOURCE", "mock").strip().lower()
    if data_source == "mock":
        print("[SAFETY GUARD] Real AD access is disabled in MOCK mode.")
        print("To test locally, use mock verification: 'python bot/test_bot.py'")
        raise RuntimeError("Real AD access is disabled in MOCK mode.")

    import ldap3

    server_uri = os.getenv("AD_LDAP_SERVER", "ldap://172.17.0.220:389")
    domain = os.getenv("AD_DOMAIN", "firstassurance.co.ke")
    base_dn = os.getenv("AD_BASE_DN", "DC=firstassurance,DC=co,DC=ke")
    user = os.getenv("AD_BIND_USER", "nkibe").strip()
    password = os.getenv("AD_BIND_PASSWORD", "").strip()

    if not password:
        import getpass
        print("\n--- Active Directory Authentication Required ---")
        prompted_user = input(f"Enter AD Username [{user}]: ").strip()
        if prompted_user:
            user = prompted_user
        password = getpass.getpass(f"Enter AD Password for '{user}': ")

    if not (server_uri and user and password):
        print("[ERROR] Credentials or LDAP server missing.")
        return

    print("=" * 65)
    print("      Active Directory LDAP Connection & User Search Test")
    print("=" * 65)
    print(f"  LDAP Server : {server_uri}")
    print(f"  Domain      : {domain}")
    print(f"  Base DN     : {base_dn}")
    print("=" * 65)

    print(f"\n[1] Connecting to LDAP Server: {server_uri} ...")
    server = ldap3.Server(server_uri, get_info=ldap3.NONE, connect_timeout=5)

    username_only = user.split("@")[0].split("\\")[-1]
    candidate_binds = [
        (ldap3.NTLM, f"{domain}\\{username_only}" if domain else username_only, "NTLM"),
        (ldap3.SIMPLE, f"{username_only}@{domain}" if domain else user, "SIMPLE (UPN)"),
        (ldap3.SIMPLE, username_only, "SIMPLE (username)"),
        (ldap3.NTLM, username_only, "NTLM (username)"),
    ]

    for auth_type, bind_name, auth_name in candidate_binds:
        try:
            print(f"[*] Attempting {auth_name} authentication ({bind_name})...")
            c = ldap3.Connection(server, user=bind_name, password=password, authentication=auth_type, auto_bind=False)
            if c.bind():
                print(f"[✓] Successfully authenticated via {auth_name}!")
                conn = c
                break
        except Exception as e:
            print(f"[-] Error during {auth_name} bind: {e}")

    if not conn:
        print("\n[x] Could not authenticate with Active Directory.")
        return

    try:
        conn.search(
            search_base=base_dn,
            search_filter="(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=*))",
            search_scope=ldap3.SUBTREE,
            attributes=["sAMAccountName", "displayName", "mail", "department"],
            size_limit=10,
        )
        print(f"[✓] Found {len(conn.entries)} user(s).")
    finally:
        conn.unbind()


if __name__ == "__main__":
    test_ad()
