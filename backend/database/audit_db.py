import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("audit-db")

ROOT = Path(__file__).resolve().parent.parent.parent
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


def get_postgres_connection():
    """Attempt connecting to PostgreSQL via DATABASE_URL or individual PG_* vars."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # On this network, PostgreSQL on 172.17.0.218 is tunneled through localhost:5432.
            # Try localhost first for immediate (0.2s) response instead of waiting for external SYN timeout.
            candidate_urls = [
                db_url.replace("172.17.0.218", "localhost") if "172.17.0.218" in db_url else db_url,
                db_url,
            ]
            for target_url in candidate_urls:
                try:
                    return psycopg2.connect(target_url, connect_timeout=2, cursor_factory=RealDictCursor)
                except Exception:
                    continue

        host = os.getenv("PG_HOST", "localhost")
        port = int(os.getenv("PG_PORT", "5432"))
        db = os.getenv("PG_DATABASE", "unlock")
        user = os.getenv("PG_USER", "unlock_user")
        password = os.getenv("PG_PASSWORD", "")

        return psycopg2.connect(
            host=host,
            port=port,
            database=db,
            user=user,
            password=password,
            connect_timeout=3,
            cursor_factory=RealDictCursor,
        )
    except Exception as exc:
        logger.debug("PostgreSQL connection not available (%s), falling back to SQLite", exc)
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
                logger.warning("Failed to insert into PostgreSQL (%s). Falling back to SQLite.", e)
            finally:
                pg_conn.close()

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
    window_minutes: int = 30,
    environment: Optional[str] = None,
) -> int:
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
                          AND status IN ('FAILURE', 'BLOCKED', 'RATE_LIMITED')
                          AND action_taken IN ('UNLOCK_ATTEMPT', 'VERIFY_FAILED', 'UNAUTHORIZED_ATTEMPT', 'RATE_LIMITED_REFERRED_TO_IT')
                          AND event_timestamp >= %s
                        """,
                        (requester_name, cutoff),
                    )
                    row = cur.fetchone()
                    return row["cnt"] if row else 0
            except Exception as e:
                logger.warning("PostgreSQL count failed (%s), fallback to SQLite", e)
            finally:
                pg_conn.close()

    target_db = get_db_path(env)
    cutoff_iso = cutoff.isoformat()
    with get_sqlite_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt FROM audit_logs
            WHERE requester_name = ?
              AND status IN ('FAILURE', 'BLOCKED', 'RATE_LIMITED')
              AND action IN ('UNLOCK_ATTEMPT', 'VERIFY_FAILED', 'UNAUTHORIZED_ATTEMPT', 'RATE_LIMITED_REFERRED_TO_IT')
              AND timestamp >= ?
            """,
            (requester_name, cutoff_iso),
        )
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def check_rate_limit(
    requester_name: str,
    max_attempts: int = 3,
    window_minutes: int = 30,
    environment: Optional[str] = None,
) -> Tuple[bool, int]:
    attempts = count_recent_failed_attempts(
        requester_name, window_minutes=window_minutes, environment=environment
    )
    if attempts >= max_attempts:
        return True, attempts
    return False, attempts


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
                logger.warning("PostgreSQL query failed (%s), fallback to SQLite", e)
            finally:
                pg_conn.close()

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
