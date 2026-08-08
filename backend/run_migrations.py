"""
Database Migration Runner for AI Simulation Monitor.

Executes versioned SQL migrations in `backend/migrations/` in order.
Tracks applied migrations in the `schema_migrations` table.
Uses configuration loaded from `backend/.env`.
"""

import os
import sys
import glob
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector

# Ensure backend directory .env is loaded
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DEFAULT_DB_NAME = os.getenv("DB_NAME", "imsr")


def clean_sql_script(raw_sql: str) -> list[str]:
    """Parse raw SQL script into executable individual statements."""
    lines = []
    for line in raw_sql.splitlines():
        line_str = line.strip()
        if line_str and not line_str.startswith("--"):
            lines.append(line)

    full_clean_sql = "\n".join(lines)
    statements = []
    for stmt in full_clean_sql.split(";"):
        stmt_clean = stmt.strip()
        if stmt_clean:
            statements.append(stmt_clean)
    return statements


def run_migrations(target_db_name: str = None):
    db_name = target_db_name or os.getenv("TEST_DB_NAME") or DEFAULT_DB_NAME
    migrations_dir = Path(__file__).resolve().parent / "migrations"

    print("=" * 60)
    print(f"[MIGRATIONS] Starting migration runner for database: {db_name}")
    print(f"[MIGRATIONS] Host: {MYSQL_HOST}:{MYSQL_PORT} | User: {MYSQL_USER}")
    print(f"[MIGRATIONS] Migration directory: {migrations_dir}")
    print("=" * 60)

    # 1. Connect to MySQL server and ensure target database exists
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            autocommit=True
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[MIGRATIONS] Error connecting to MySQL server: {e}")
        sys.exit(1)

    # 2. Connect to the target database with autocommit=True for DDL safety
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=db_name,
            autocommit=True
        )
        cursor = conn.cursor()
    except Exception as e:
        print(f"[MIGRATIONS] Error connecting to database `{db_name}`: {e}")
        sys.exit(1)

    # 3. Create schema_migrations tracking table if it doesn't exist
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `schema_migrations` (
                `version` VARCHAR(255) PRIMARY KEY,
                `applied_at` DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    except Exception as e:
        print(f"[MIGRATIONS] Error creating schema_migrations table: {e}")
        sys.exit(1)

    # 4. Fetch list of already applied migrations
    cursor.execute("SELECT `version` FROM `schema_migrations`;")
    applied_versions = {row[0] for row in cursor.fetchall()}

    # 5. Discover migration files (.sql) sorted by filename
    migration_files = sorted(glob.glob(str(migrations_dir / "*.sql")))

    if not migration_files:
        print("[MIGRATIONS] No migration files found.")
        return

    applied_count = 0
    skipped_count = 0

    for file_path in migration_files:
        filename = os.path.basename(file_path)

        if filename in applied_versions:
            print(f"  • {filename} ... SKIPPED (Already applied)")
            skipped_count += 1
            continue

        print(f"  • Applying {filename} ... ", end="", flush=True)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_sql = f.read()

            statements = clean_sql_script(raw_sql)

            for stmt in statements:
                cursor.execute(stmt)

            # Record migration in tracking table
            cursor.execute(
                "INSERT INTO `schema_migrations` (`version`, `applied_at`) VALUES (%s, %s);",
                (filename, datetime.utcnow())
            )
            print("OK")
            applied_count += 1
        except Exception as e:
            print("FAILED")
            print(f"\n[MIGRATIONS ERROR] Migration {filename} failed: {e}")
            sys.exit(1)

    cursor.close()
    conn.close()

    print("-" * 60)
    print(f"[MIGRATIONS SUMMARY] Done! {applied_count} applied, {skipped_count} skipped.")
    print("=" * 60)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_migrations(target)
