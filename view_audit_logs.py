import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.database.audit_db import (
    get_audit_logs,
    get_current_environment,
    get_db_path,
    get_target_schema,
    is_postgres_configured,
)


def main():
    target_env = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().upper()
        if arg in ("UAT", "PROD", "PRODUCTION"):
            target_env = "PRODUCTION" if arg in ("PROD", "PRODUCTION") else "UAT"
        else:
            target_env = arg

    active_env = target_env or get_current_environment()
    schema = get_target_schema(active_env)
    is_pg = is_postgres_configured()

    db_desc = f"PostgreSQL [{schema}.account_unlock_audit]" if is_pg else f"SQLite ({get_db_path(active_env)})"

    print("=" * 115)
    print(f"               FIRST ASSURANCE IT ACCOUNT UNLOCK - SQL AUDIT LOG VIEWER [{active_env}]")
    print(f" Active Database: {db_desc}")
    print("=" * 115)

    logs = get_audit_logs(limit=100, environment=active_env)
    if not logs:
        print(f"\n [i] No audit logs recorded yet in '{active_env}' ({db_desc}).\n")
        print("=" * 115)
        return

    # Header format
    header = (
        f"{'ID':<4} | {'Timestamp':<19} | {'Requester':<18} | {'Target Account':<16} | "
        f"{'Action':<24} | {'Status':<12} | {'Env':<6} | {'Details'}"
    )
    print(header)
    print("-" * 115)

    for entry in logs:
        ts = entry["timestamp"][:19] if entry.get("timestamp") else "N/A"
        req = (entry.get("requester_name") or "Unknown")[:17]
        target_name = entry.get("target_account_name") or "N/A"
        target_id = entry.get("target_account_id") or "N/A"
        target = f"{target_name} ({target_id})" if target_id != "N/A" else target_name
        target = target[:15]
        action = (entry.get("action") or "")[:23]
        status = (entry.get("status") or "")[:11]
        env = (entry.get("environment") or "")[:6]
        details = (entry.get("details") or "")[:30]

        print(
            f"{entry['id']:<4} | {ts:<19} | {req:<18} | {target:<16} | "
            f"{action:<24} | {status:<12} | {env:<6} | {details}"
        )

    print("-" * 115)
    print(f" Total records displayed: {len(logs)} (Environment: {active_env})")
    print("=" * 115)


if __name__ == "__main__":
    main()
