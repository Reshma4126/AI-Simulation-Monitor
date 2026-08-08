"""MySQL async connection via aiomysql -- loads from .env."""

import os
import ssl
import json
from dotenv import load_dotenv
import aiomysql

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "imsr")
MYSQL_SSL = os.getenv("MYSQL_SSL", "false" if MYSQL_HOST in ("localhost", "127.0.0.1") else "true").lower() in ("true", "1", "yes")

# -----------------------------
# SSL Context for TiDB Cloud / Remote MySQL
# -----------------------------
if MYSQL_SSL:
    ca_path = os.path.join(os.path.dirname(__file__), "certs", "isrgrootx1.pem")
    if os.path.exists(ca_path):
        ssl_ctx = ssl.create_default_context(cafile=ca_path)
    else:
        ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
else:
    ssl_ctx = None

# Connection pool
pool = None


async def init_db():
    """Connect to database and create tables if they don't exist."""
    global pool

    # Create the database if it doesn't exist
    temp_pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        autocommit=True,
        ssl=ssl_ctx
    )
    async with temp_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    temp_pool.close()
    await temp_pool.wait_closed()

    # Create connection pool
    pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=DB_NAME,
        autocommit=True,
        ssl=ssl_ctx
    )

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:

            # Users table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    created_at DATETIME NOT NULL
                )
            """)

            # Scenarios table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    patient_details JSON NOT NULL,
                    symptoms JSON NOT NULL,
                    initial_readings JSON NOT NULL
                )
            """)

            # Sessions table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_code VARCHAR(50) UNIQUE NOT NULL,
                    created_by INT NOT NULL,
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    event_log JSON,
                    history JSON,
                    current_scenario_id INT,
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (current_scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL
                )
            """)

            # Monitor State table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS monitor_state (
                    session_id INT PRIMARY KEY,
                    state_data JSON,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Debrief Reports table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS debrief_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id INT NULL,
                    session_code VARCHAR(50) NOT NULL UNIQUE,
                    overall_score FLOAT,
                    grade VARCHAR(10),
                    status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
                    debrief_data JSON,
                    pdf_path VARCHAR(255),
                    error_message TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
                )
            """)

            # Add current_scenario_id if missing
            await cur.execute(
                "SHOW COLUMNS FROM sessions LIKE 'current_scenario_id'"
            )
            has_col = await cur.fetchone()

            if not has_col:
                try:
                    await cur.execute(
                        "ALTER TABLE sessions ADD COLUMN current_scenario_id INT NULL"
                    )

                    await cur.execute("""
                        ALTER TABLE sessions
                        ADD CONSTRAINT fk_sessions_scenarios
                        FOREIGN KEY (current_scenario_id)
                        REFERENCES scenarios(id)
                        ON DELETE SET NULL
                    """)

                except Exception as e:
                    print(f"[DB] Info: {e}")

            # Seed scenarios if empty
            await cur.execute("SELECT COUNT(*) FROM scenarios")
            count_res = await cur.fetchone()

            if count_res and count_res[0] == 0:

                print("[SEED] Seeding scenarios...")

                json_path = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "patient_monitor_scenarios_20.json"
                    )
                )

                if os.path.exists(json_path):

                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    scenarios_to_seed = []

                    for idx, sc in enumerate(data.get("scenarios", [])):

                        pd = sc.get("patientDetails", {})
                        symp = sc.get("symptoms", {})
                        mv = sc.get("monitorValues", {})

                        name = pd.get(
                            "patientName",
                            f"Scenario {idx + 1}"
                        )

                        scenarios_to_seed.append((
                            name,
                            json.dumps(pd),
                            json.dumps(symp),
                            json.dumps(mv)
                        ))

                    if scenarios_to_seed:

                        await cur.executemany(
                            """
                            INSERT INTO scenarios
                            (name, patient_details, symptoms, initial_readings)
                            VALUES (%s,%s,%s,%s)
                            """,
                            scenarios_to_seed
                        )

                        print(
                            f"[SEED] Seeded {len(scenarios_to_seed)} scenarios."
                        )

                else:

                    print(
                        f"[SEED] JSON not found at {json_path}"
                    )

    print(f"[DB] Connected to TiDB Cloud — database: {DB_NAME}")


async def get_db_pool():
    global pool
    return pool


async def save_debrief_report_async(report_data: dict) -> bool:
    """
    Save or update a debrief report record in MySQL database.
    """
    session_code = str(report_data.get("session_code", report_data.get("session_id", "UNKNOWN")))
    overall_score = float(report_data.get("overall_score", 0.0))
    grade = str(report_data.get("grade", "N/A"))
    status = str(report_data.get("status", "COMPLETED"))
    debrief_data_json = json.dumps(report_data.get("debrief_data", report_data))
    pdf_path = str(report_data.get("pdf_path", ""))
    error_message = report_data.get("error_message")
    from datetime import datetime
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = await aiomysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=DB_NAME,
            autocommit=True,
            ssl=ssl_ctx
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # Find matching session_id if exists in sessions table, or create session record
                await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
                sess_row = await cur.fetchone()
                if sess_row:
                    db_session_id = sess_row["id"]
                else:
                    await cur.execute("SELECT id FROM users LIMIT 1")
                    user_row = await cur.fetchone()
                    user_id = user_row["id"] if user_row else 1
                    try:
                        await cur.execute(
                            "INSERT INTO sessions (session_code, created_by, started_at, is_active) VALUES (%s, %s, %s, 0)",
                            (session_code, user_id, now_str)
                        )
                        db_session_id = cur.lastrowid
                    except Exception:
                        await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
                        sess_row = await cur.fetchone()
                        db_session_id = sess_row["id"] if sess_row else None

                query = """
                    INSERT INTO debrief_reports
                    (session_id, session_code, overall_score, grade, status, debrief_data, pdf_path, error_message, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    session_id = VALUES(session_id),
                    overall_score = VALUES(overall_score),
                    grade = VALUES(grade),
                    status = VALUES(status),
                    debrief_data = VALUES(debrief_data),
                    pdf_path = VALUES(pdf_path),
                    error_message = VALUES(error_message),
                    updated_at = VALUES(updated_at)
                """
                await cur.execute(query, (
                    db_session_id, session_code, overall_score, grade, status,
                    debrief_data_json, pdf_path, error_message, now_str, now_str
                ))
                print(f"[DB] Debrief report saved/updated successfully in MySQL for session_code: {session_code}")
                return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB] Error saving debrief report for {session_code}: {e}")
        return False


def save_debrief_report_sync(report_data: dict) -> bool:
    """Synchronous wrapper for save_debrief_report_async."""
    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(save_debrief_report_async(report_data))
            return True
        else:
            return asyncio.run(save_debrief_report_async(report_data))
    except Exception as e:
        print(f"[DB] Error in save_debrief_report_sync: {e}")
        return False

