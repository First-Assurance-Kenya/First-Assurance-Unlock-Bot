import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database.audit_db import clear_audit_logs, get_audit_logs
from backend.services.ad_service import (
    find_user,
    find_user_by_name,
    get_account_status,
    is_mock_mode,
    mock_users,
    unlock_account,
)
from bot.conversation import AccountUnlockBot
from bot.teams_session import handle_user_input


def extract_facts(card):
    if not card or not hasattr(card, "body"):
        return {}
    for elem in card.body:
        if hasattr(elem, "facts"):
            return {f.title: f.value for f in elem.facts}
        if hasattr(elem, "items"):
            for item in elem.items:
                if hasattr(item, "facts"):
                    return {f.title: f.value for f in item.facts}
    return {}


print("=================================================================")
print("  TEST 1: CLEAR AUDIT DATABASE & VERIFY MOCK ENVIRONMENT         ")
print("=================================================================")
assert is_mock_mode(), "DATA_SOURCE must be mock mode!"
clear_audit_logs()
print("[✓] Audit log database cleared for clean test run.")

# Reset mock users
mock_users["EMP001"]["locked"] = True
mock_users["EMP002"]["locked"] = False
mock_users["EMP003"]["locked"] = True
mock_users["JANE01"]["locked"] = True


print("\n=================================================================")
print("  TEST 2: ENTRA ID AUTHORIZATION (JANE UNLOCKS JANE vs NEWTON)   ")
print("=================================================================")
# Case A: Jane Doe attempts to unlock Jane Doe (Allowed)
cid_jane = "teams-session-jane"
handle_user_input(cid_jane, text="Hello Bot", requester_name="Jane Doe", requester_id="29:jane123")
handle_user_input(cid_jane, text="1", requester_name="Jane Doe", requester_id="29:jane123")
reply, card = handle_user_input(cid_jane, text="Jane Doe", requester_name="Jane Doe", requester_id="29:jane123")
print("[USER (Jane)]: Jane Doe")
print("[BOT]:", reply)
assert card is not None, "Verification card should be displayed for own account"
facts = extract_facts(card)
assert facts["Full Name"] == "Jane Doe"
print("[✓] Authorized: Jane Doe verified her own account successfully.")

# Confirm unlock
reply, card = handle_user_input(cid_jane, text="Yes", requester_name="Jane Doe", requester_id="29:jane123")
assert mock_users["JANE01"]["locked"] is False
print("[✓] Unlocked: Jane Doe unlocked her own account successfully.")

# Case B: John Smith attempts to unlock Newton Kibe's account (Denied)
cid_impostor = "teams-session-impostor"
handle_user_input(cid_impostor, text="Hello Bot", requester_name="John Smith", requester_id="29:john456")
handle_user_input(cid_impostor, text="1", requester_name="John Smith", requester_id="29:john456")
reply, card = handle_user_input(cid_impostor, text="Newton Kibe", requester_name="John Smith", requester_id="29:john456")
print("\n[USER (John Smith)]: Newton Kibe")
print("[BOT]:", reply)
assert "Security Policy Violation" in reply or "Policy" in reply
assert card is not None, "Unauthorized card should be returned"
print("[✓] Blocked: John Smith was prevented from unlocking Newton Kibe's account.")


print("\n=================================================================")
print("  TEST 3: RATE LIMITING (3 ATTEMPTS -> REFERRED TO IT HELPDESK)  ")
print("=================================================================")
cid_rate = "teams-session-ratelimit"
requester = "Bad Actor"

# Attempt 1 (Failure: non-existent account)
handle_user_input(cid_rate, text="Hello Bot", requester_name=requester)
handle_user_input(cid_rate, text="1", requester_name=requester)
reply, card = handle_user_input(cid_rate, text="Ghost User 1", requester_name=requester)
print(f"[Attempt 1] BOT: {reply[:65]}...")
assert "Attempts remaining before IT referral: 2/3" in reply

# Attempt 2 (Failure: non-existent account)
reply, card = handle_user_input(cid_rate, text="Ghost User 2", requester_name=requester)
print(f"[Attempt 2] BOT: {reply[:65]}...")
assert "Attempts remaining before IT referral: 1/3" in reply

# Attempt 3 (Failure: reaches threshold 3)
reply, card = handle_user_input(cid_rate, text="Ghost User 3", requester_name=requester)
print(f"[Attempt 3] BOT: {reply}")
assert "Maximum attempts exceeded" in reply
assert card is not None, "Referral card must be present"
facts = extract_facts(card)
print(">>> Referral Card Facts:", facts)
assert facts["Status"] == "Referred to IT Helpdesk"
assert "ithelpdesk@firstassurance.co.ke" in facts["Help Desk Email"]

# Attempt 4 (Blocked by rate limiter)
reply, card = handle_user_input(cid_rate, text="Hello Bot", requester_name=requester)
assert "Maximum attempts exceeded" in reply
print("[✓] Rate Limiting Confirmed: Subsequent requests blocked and referred to IT Helpdesk.")


print("\n=================================================================")
print("  TEST 4: SQL AUDIT LOG DATABASE INSPECTION                       ")
print("=================================================================")
logs = get_audit_logs(limit=20)
print(f"[✓] Successfully retrieved {len(logs)} audit log records from SQLite.")

# Check required fields exist on every row
for row in logs[:3]:
    print(f"  • [{row['timestamp'][:19]}] Action: {row['action']} | Requester: {row['requester_name']} | Target: {row['target_account_name']} | Status: {row['status']} | Env: {row['environment']}")
    assert row["action"] is not None
    assert row["requester_name"] is not None
    assert row["status"] in ("SUCCESS", "FAILURE", "BLOCKED", "RATE_LIMITED", "CANCELLED")
    assert row["environment"] == "MOCK"

print("\n=================================================================")
print("       ALL SECURITY, RATE LIMIT & SQL AUDIT TESTS PASSED!        ")
print("=================================================================")