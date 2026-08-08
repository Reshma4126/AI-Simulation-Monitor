import asyncio
import aiomysql
import json
import traceback
from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
from debrief_adapter import convert_and_debrief

async def debug():
    conn = await aiomysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD, db=DB_NAME, autocommit=True, ssl=ssl_ctx
    )
    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM sessions WHERE session_code = 'R04ZOG'")
            session = await cur.fetchone()
            print("Session found:", session["session_code"] if session else None)

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            monitor_state = json.loads(state_row["state_data"]) if state_row else {}

            raw_log = json.loads(session["event_log"]) if session.get("event_log") else []

            print("\nRunning convert_and_debrief...")
            try:
                res = convert_and_debrief(session, raw_log, monitor_state)
                print("SUCCESS!", res.keys())
            except Exception as e:
                print("EXCEPTION CAPTURED:")
                traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(debug())
