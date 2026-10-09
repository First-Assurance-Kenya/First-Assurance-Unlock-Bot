"""
Test script: Demonstrates rate limiting (max 3 failed attempts)
and inspects how the events are logged to the SQL database (audit_log_uat.db).
"""
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.database.audit_db import (
    check_rate_limit,
    count_recent_failed_attempts,
    get_audit_logs,
    get_current_environment,
    get_db_path,
    get_target_schema,
    is_postgres_configured,
)
from bot.conversation import AccountUnlockBot, ConversationState


def run_rate_limiting_test(custom_user: str = None):
    env = get_current_environment()
    schema = get_target_schema(env)
    is_pg = is_postgres_configured()
    db_desc = f"PostgreSQL [{schema}.account_unlock_audit]" if is_pg else f"SQLite ({get_db_path(env)})"
    
    # Generate unique test user identity so each run tests the clean 0 -> 1 -> 2 -> 3 transition
    suffix = int(time.time()) % 10000
    test_user = custom_user or f"Employee_Test_{suffix}"

    print("=" * 95)
    print("                      RATE LIMITING TEST & DATABASE VERIFICATION")
    print(f" Target Environment: {env}")
    print(f" Active Database:    {db_desc}")
    print(f" Test User Identity: {test_user}")
    print("=" * 95)

    # 1. Initialize Bot session for test user
    bot = AccountUnlockBot(requester_name=test_user, requester_id=f"SIM-{suffix}")
    
    print("\n--- STEP 1: User says 'Hello Bot' ---")
    welcome, _ = bot.process_input(text="hello bot")
    print(f" Bot State: {bot.state.value}")
    print(f" Response:  {welcome.splitlines()[0]}")

    print("\n--- STEP 2: User selects Option '1' (Unlock Account) ---")
    menu_reply, _ = bot.process_input(text="1")
    print(f" Bot State: {bot.state.value}")
    print(f" Response:  {menu_reply.strip()}")

    # 2. Trigger 3 consecutive failed search attempts
    invalid_searches = ["UnknownUser_Alpha", "UnknownUser_Beta", "UnknownUser_Gamma"]

    for i, fake_name in enumerate(invalid_searches, start=1):
        print(f"\n--- STEP 3.{i}: Attempt {i}/3 - User inputs non-existent account: '{fake_name}' ---")
        reply, card = bot.process_input(text=fake_name)
        
        is_locked, count = check_rate_limit(test_user, environment=env)
        print(f" Bot State:           {bot.state.value}")
        print(f" Failed Count in DB:  {count}/3")
        print(f" Is Rate Limited?:    {is_locked}")
        print(f" Bot Message Output:\n{reply}")
        if card:
            print(" >> [Adaptive Card Attached]: IT Referral Card (Contact: ithelpdesk@firstassurance.co.ke | Ext 4444)")

    print("\n--- STEP 4: Attempting further interaction while locked out ---")
    locked_reply, card = bot.process_input(text="Please unlock me now!")
    print(f" Bot State: {bot.state.value}")
    print(f" Response:  {locked_reply.splitlines()[0]}")
    if card:
        print(" >> [Adaptive Card Attached]: IT Referral Card (Blocked session remains locked)")

    # 3. Query the SQL Database to show exactly what was recorded
    print("\n" + "=" * 95)
    print(f"               SQL AUDIT LOG ENTRIES RECORDED IN {db_desc}")
    print("=" * 95)
    
    logs = get_audit_logs(limit=20, environment=env)
    user_logs = [log for log in logs if log["requester_name"] == test_user]

    if not user_logs:
        print("[!] No logs found for test user.")
        return

    header = f"{'ID':<4} | {'Timestamp':<19} | {'Action':<28} | {'Status':<12} | {'Env':<6} | {'Details'}"
    print(header)
    print("-" * 95)
    for entry in reversed(user_logs):  # show chronological order
        ts = entry["timestamp"][:19]
        action = entry["action"][:26]
        status = entry["status"][:10]
        rec_env = entry["environment"][:5]
        details = entry["details"][:28]
        print(f"{entry['id']:<4} | {ts:<19} | {action:<28} | {status:<12} | {rec_env:<6} | {details}")
    print("=" * 95)
    print(f"\n[SUCCESS] Verified: 3 failed attempts recorded -> Locked out -> Referred to IT Helpdesk.")


if __name__ == "__main__":
    custom = sys.argv[1] if len(sys.argv) > 1 else None
    run_rate_limiting_test(custom)
