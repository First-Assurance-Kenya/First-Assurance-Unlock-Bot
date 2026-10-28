import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

logger = logging.getLogger("audit-db")

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")
DB_DIR = ROOT / "data"


def get_current_environment() -> str:
    """
    Return active environment: 'UAT' (default) or 'PRODUCTION'.
    Reads ENVIRONMENT or APP_ENV from environment variables.
    """
    env = os.getenv("ENVIRONMENT") or os.getenv("APP_ENV")
    if env:
        clean = env.strip().upper()
        if clean in ("PROD", "PRODUCTION"):
            return "PRODUCTION"
        return clean

    data_source = os.getenv("DATA_SOURCE", "mock").strip().lower()
    return "PRODUCTION" if data_source == "real" else "UAT"


def get_target_schema(env: Optional[str] = None) -> str:
    """Return target PostgreSQL schema ('uat' or 'prod')."""
    target_env = (env or get_current_environment()).upper()
    return "prod" if target_env in ("PROD", "PRODUCTION") else "uat"


# -----------------------------------------------------------------------------
# PostgreSQL Database Support
# -----------------------------------------------------------------------------

def is_postgres_configured() -> bool:
    """Check if PostgreSQL environment variables are configured."""
    return bool(os.getenv("DATABASE_URL") or os.getenv("PG_HOST") or os.getenv("PG_DATABASE"))


_persistent_pg_conn = None


def get_postgres_connection():
    """Maintain a fast, persistent PostgreSQL connection to avoid connection lag."""
    global _persistent_pg_conn
    if _persistent_pg_conn is not None:
        try:
            if not _persistent_pg_conn.closed:
                return _persistent_pg_conn
        except Exception:
            _persistent_pg_conn = None

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_url = os.getenv("DATABASE_URL")
        candidate_urls = []
        if db_url:
            candidate_urls.append(db_url)
            if "172.17.0.218" in db_url:
                candidate_urls.append(db_url.replace("172.17.0.218", "localhost"))
            elif "localhost" in db_url:
                candidate_urls.append(db_url.replace("localhost", "172.17.0.218"))

        for target_url in candidate_urls:
            try:
                conn = psycopg2.connect(target_url, connect_timeout=3, cursor_factory=RealDictCursor)
                conn.autocommit = True
                _persistent_pg_conn = conn
                logger.info("Connected to PostgreSQL at %s", target_url.split("@")[-1])
                return _persistent_pg_conn
            except Exception:
                continue
    except Exception as exc:
        logger.debug("PostgreSQL connection not available (%s), falling back to SQLite", exc)
        return None
    return None


# -----------------------------------------------------------------------------
# SQLite Fallback Support
# -----------------------------------------------------------------------------

def get_db_path(env: Optional[str] = None) -> Path:
    target_env = (env or get_current_environment()).upper()
    if target_env in ("PROD", "PRODUCTION"):
        filename = "audit_log_prod.db"
    elif target_env == "UAT":
        filename = "audit_log_uat.db"
    else:
        filename = f"audit_log_{target_env.lower()}.db"

    override = os.getenv("AUDIT_DB_PATH")
    if override and not env:
        return Path(override).resolve()

    return DB_DIR / filename


def get_sqlite_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize local SQLite database tables."""
    with get_sqlite_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                requester_name TEXT NOT NULL,
                requester_id TEXT,
                target_account_id TEXT,
                target_account_name TEXT,
                target_department TEXT,
                status TEXT NOT NULL,
                environment TEXT NOT NULL,
                details TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs (timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_req ON audit_logs (requester_name, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs (target_account_id, timestamp)")
        conn.commit()


init_db()


# -----------------------------------------------------------------------------
# Unified Audit Logging (Routes to PostgreSQL if configured, else SQLite)
# -----------------------------------------------------------------------------

def log_audit_event(
    action: str,
    requester_name: str,
    status: str,
    requester_id: Optional[str] = None,
    target_account_id: Optional[str] = None,
    target_account_name: Optional[str] = None,
    target_department: Optional[str] = None,
    details: Optional[str] = None,
    environment: Optional[str] = None,
) -> int:
    env = environment or get_current_environment()
    schema = get_target_schema(env)
    now_iso = datetime.now().isoformat()

    # Try PostgreSQL first if configured
    if is_postgres_configured():
        pg_conn = get_postgres_connection()
        if pg_conn:
            try:
                with pg_conn:
                    with pg_conn.cursor() as cur:
                        table = f"{schema}.account_unlock_audit"
                        target = target_account_name or target_account_id or "N/A"
                        cur.execute(
                            f"""
                            INSERT INTO {table} (
                                event_timestamp, target_account, requested_by,
                                action_taken, status, error_message, environment
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING audit_id
                            """,
                            (
                                now_iso,
                                target,
                                requester_name,
                                action,
                                status,
                                details or "",
                                env,
                            ),
                        )
                        row = cur.fetchone()
                        last_id = row["audit_id"] if row else 0
                        logger.info("Logged audit event #%s to PostgreSQL [%s.%s]", last_id, schema, table)
                        return last_id
            except Exception as e:
                global _persistent_pg_conn
                _persistent_pg_conn = None
                logger.warning("Failed to insert into PostgreSQL (%s). Falling back to SQLite.", e)

    # Fallback to SQLite
    target_db = get_db_path(env)
    init_db(target_db)
    with get_sqlite_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (
                timestamp, action, requester_name, requester_id,
                target_account_id, target_account_name, target_department,
                status, environment, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso,
                action,
                requester_name,
                requester_id or "N/A",
                target_account_id or "N/A",
                target_account_name or "N/A",
                target_department or "N/A",
                status,
                env,
                details or "",
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def count_recent_failed_attempts(
    requester_name: str,
    window_minutes: int = 1440,
    environment: Optional[str] = None,
) -> int:
    """Count unlock requests and failed attempts within the 24-hour daily window."""
    env = environment or get_current_environment()
    schema = get_target_schema(env)
    cutoff = datetime.now() - timedelta(minutes=window_minutes)

    if is_postgres_configured():
        pg_conn = get_postgres_connection()
        if pg_conn:
            try:
                with pg_conn.cursor() as cur:
                    table = f"{schema}.account_unlock_audit"
                    cur.execute(
                        f"""
                        SELECT COUNT(*) AS cnt FROM {table}
                        WHERE requested_by = %s
                          AND action_taken IN ('UNLOCK_SUCCESS', 'UNLOCK_ATTEMPT', 'UNLOCK_FAILED', 'VERIFY_FAILED', 'UNAUTHORIZED_ATTEMPT')
                          AND event_timestamp >= %s
                        """,
                        (requester_name, cutoff),
                    )
                    row = cur.fetchone()
                    return row["cnt"] if row else 0
            except Exception as e:
                global _persistent_pg_conn
                _persistent_pg_conn = None
                logger.warning("PostgreSQL count failed (%s), fallback to SQLite", e)

    target_db = get_db_path(env)
    cutoff_iso = cutoff.isoformat()
    with get_sqlite_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt FROM audit_logs
            WHERE requester_name = ?
              AND action IN ('UNLOCK_SUCCESS', 'UNLOCK_ATTEMPT', 'UNLOCK_FAILED', 'VERIFY_FAILED', 'UNAUTHORIZED_ATTEMPT')
              AND timestamp >= ?
            """,
            (requester_name, cutoff_iso),
        )
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def check_rate_limit(
    requester_name: str,
    max_attempts: int = 3,
    window_minutes: int = 1440,
    environment: Optional[str] = None,
) -> Tuple[bool, int]:
    """Check if requester has exceeded the 3 daily unlock requests limit (24 hours)."""
    attempts = count_recent_failed_attempts(
        requester_name, window_minutes=window_minutes, environment=environment
    )
    if attempts >= max_attempts:
        return True, attempts
    return False, attempts


def get_sponsored_colleagues_today(
    requester_name: str,
    window_minutes: int = 1440,
    environment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve all distinct colleagues unlocked by this requester in the past 24 hours.
    Returns: [{'colleague_name': str, 'target_id': str, 'unlock_count': int, 'latest_time': str}, ...]
    Filters out self-unlocks (where requester unlocked their own account).
    """
    env = environment or get_current_environment()
    schema = get_target_schema(env)
    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    req_clean = (requester_name or "").strip().lower()

    if is_postgres_configured():
        pg_conn = get_postgres_connection()
        if pg_conn:
            try:
                with pg_conn.cursor() as cur:
                    table = f"{schema}.account_unlock_audit"
                    cur.execute(
                        f"""
                        SELECT 
                            target_account,
                            COUNT(*) AS unlock_count,
                            MAX(event_timestamp) AS latest_time
                        FROM {table}
                        WHERE requested_by = %s
                          AND action_taken = 'UNLOCK_SUCCESS'
                          AND status = 'SUCCESS'
                          AND event_timestamp >= %s
                        GROUP BY target_account
                        ORDER BY latest_time DESC
                        """,
                        (requester_name, cutoff),
                    )
                    rows = cur.fetchall()
                    sponsored = []
                    for row in rows:
                        tgt = (row["target_account"] or "").strip()
                        tgt_lower = tgt.lower()
                        # Filter out self-unlocks (where target name contains requester or vice versa)
                        if req_clean and (tgt_lower == req_clean or req_clean in tgt_lower or tgt_lower in req_clean):
                            continue
                        sponsored.append({
                            "colleague_name": tgt,
                            "target_id": tgt,
                            "unlock_count": row["unlock_count"],
                            "latest_time": str(row["latest_time"]),
                        })
                    return sponsored
            except Exception as e:
                global _persistent_pg_conn
                _persistent_pg_conn = None
                logger.warning("PostgreSQL get_sponsored_colleagues failed (%s), fallback to SQLite", e)

    target_db = get_db_path(env)
    cutoff_iso = cutoff.isoformat()
    with get_sqlite_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                target_account_name,
                target_account_id,
                COUNT(*) AS unlock_count,
                MAX(timestamp) AS latest_time
            FROM audit_logs
            WHERE requester_name = ?
              AND action = 'UNLOCK_SUCCESS'
              AND status = 'SUCCESS'
              AND timestamp >= ?
            GROUP BY target_account_name, target_account_id
            ORDER BY latest_time DESC
            """,
            (requester_name, cutoff_iso),
        )
        rows = cursor.fetchall()
        sponsored = []
        for row in rows:
            tgt_name = (row["target_account_name"] or "").strip()
            tgt_id = (row["target_account_id"] or "").strip()
            tgt = tgt_name or tgt_id
            tgt_lower = tgt.lower()
            if req_clean and (tgt_lower == req_clean or req_clean in tgt_lower or tgt_lower in req_clean):
                continue
            sponsored.append({
                "colleague_name": tgt_name,
                "target_id": tgt_id,
                "unlock_count": row["unlock_count"],
                "latest_time": str(row["latest_time"]),
            })
        return sponsored


def check_colleague_sponsorship_limit(
    requester_name: str,
    target_name: str,
    target_id: Optional[str] = None,
    max_unlocks_per_colleague: int = 3,
    window_minutes: int = 1440,
    environment: Optional[str] = None,
) -> Tuple[bool, str, int, Optional[str]]:
    """
    Check if requester is allowed to unlock for this specific colleague.
    Rule: An employee can ONLY unlock for ONE distinct colleague per 24 hours (up to 3 times).

    Returns: (is_allowed: bool, reason: str, count: int, current_sponsored_colleague: Optional[str])
    Reasons:
      - "ALLOWED_FIRST": Requester has not unlocked any colleague yet today.
      - "ALLOWED_SAME": Requester is unlocking the same colleague they already assisted (< 3 times).
      - "DIFFERENT_COLLEAGUE": Requester has already unlocked a different colleague today.
      - "COLLEAGUE_LIMIT_REACHED": Requester has already unlocked this colleague 3 times today.
    """
    colleagues = get_sponsored_colleagues_today(
        requester_name, window_minutes=window_minutes, environment=environment
    )
    if not colleagues:
        return True, "ALLOWED_FIRST", 0, None

    primary = colleagues[0]
    sponsored_name = primary["colleague_name"]
    sponsored_id = primary.get("target_id") or ""
    unlock_count = primary["unlock_count"]

    tgt_clean = (target_name or "").strip().lower()
    tgt_id_clean = (target_id or "").strip().lower()
    spon_clean = sponsored_name.strip().lower()
    spon_id_clean = sponsored_id.strip().lower()

    matches = (
        tgt_clean in spon_clean
        or spon_clean in tgt_clean
        or (tgt_id_clean and tgt_id_clean == spon_id_clean)
        or (tgt_id_clean and tgt_id_clean in spon_clean)
        or (spon_clean and spon_clean in tgt_clean)
    )

    if not matches:
        return False, "DIFFERENT_COLLEAGUE", unlock_count, sponsored_name

    if unlock_count >= max_unlocks_per_colleague:
        return False, "COLLEAGUE_LIMIT_REACHED", unlock_count, sponsored_name

    return True, "ALLOWED_SAME", unlock_count, sponsored_name


def reset_rate_limit(requester_name: str, environment: Optional[str] = None) -> None:
    """Clear failed attempts for a user (useful for admin testing)."""
    env = environment or get_current_environment()
    target_db = get_db_path(env)
    try:
        with get_sqlite_connection(target_db) as conn:
            conn.execute(
                "DELETE FROM audit_logs WHERE requester_name = ? AND status IN ('FAILURE', 'BLOCKED', 'RATE_LIMITED')",
                (requester_name,),
            )
            conn.commit()
    except Exception:
        pass


def clear_audit_logs(environment: Optional[str] = None) -> None:
    """Clear all audit logs (useful for test suites)."""
    env = environment or get_current_environment()
    schema = get_target_schema(env)
    if is_postgres_configured():
        pg_conn = get_postgres_connection()
        if pg_conn:
            try:
                with pg_conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE {schema}.account_unlock_audit RESTART IDENTITY")
                return
            except Exception:
                pass
    target_db = get_db_path(env)
    if target_db.exists():
        with get_sqlite_connection(target_db) as conn:
            conn.execute("DELETE FROM audit_logs")
            conn.commit()


def get_audit_logs(limit: int = 50, environment: Optional[str] = None) -> List[Dict[str, Any]]:
    env = environment or get_current_environment()
    schema = get_target_schema(env)

    if is_postgres_configured():
        pg_conn = get_postgres_connection()
        if pg_conn:
            try:
                with pg_conn.cursor() as cur:
                    table = f"{schema}.account_unlock_audit"
                    cur.execute(
                        f"""
                        SELECT audit_id AS id, event_timestamp::text AS timestamp,
                               action_taken AS action, requested_by AS requester_name,
                               target_account AS target_account_name,
                               status, environment, error_message AS details
                        FROM {table}
                        ORDER BY audit_id DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    return [dict(r) for r in cur.fetchall()]
            except Exception as e:
                global _persistent_pg_conn
                _persistent_pg_conn = None
                logger.warning("PostgreSQL query failed (%s), fallback to SQLite", e)

    target_db = get_db_path(env)
    if not target_db.exists():
        return []

    with get_sqlite_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, action, requester_name, requester_id,
                   target_account_id, target_account_name, target_department,
                   status, environment, details
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
