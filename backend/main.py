"""FastAPI app + Socket.IO mount -- main entry point."""

import random
import string
import json
import traceback
from datetime import datetime
from contextlib import asynccontextmanager

import socketio
import aiomysql
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_instructor,
)
from database import (
    init_db,
    get_db_pool
)
from models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    DEFAULT_MONITOR_STATE,
    PARAMETER_SPEC,
)
from ecg_state import ECGStateUpdate
from socket_manager import sio, emit_session_ended, load_scenarios_to_cache
from simman_engine.state_machine import engine
from simman_engine.rhythm_intelligence import intelligence_payload


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await load_scenarios_to_cache()
    await engine.start()
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT username FROM users WHERE username IN ('instructor', 'student')")
            existing_rows = await cur.fetchall()
            existing_users = {r["username"] for r in existing_rows}

            if "instructor" not in existing_users:
                await cur.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                    ("instructor", hash_password("instructor123"), "instructor", datetime.utcnow())
                )
            if "student" not in existing_users:
                await cur.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                    ("student", hash_password("student123"), "student", datetime.utcnow())
                )
            await conn.commit()

            await cur.execute("SELECT COUNT(*) as count FROM users")
            res = await cur.fetchone()
            print(f"[INIT] Users in database: {res['count']}")
    yield
    await engine.stop()



# ── App Setup ─────────────────────────────────────────────────────

api_app = FastAPI(title="AI Simulation Monitor", lifespan=lifespan)

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth Routes ───────────────────────────────────────────────────

@api_app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username = %s", (body.username,))
            user = await cur.fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
    })

    session_code = None
    if user["role"] == "instructor":
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT session_code FROM sessions WHERE created_by = %s AND is_active = 1", 
                    (user["id"],)
                )
                session = await cur.fetchone()
                if session:
                    session_code = session["session_code"]

    return TokenResponse(
        access_token=token,
        role=user["role"],
        session_code=session_code,
    )


@api_app.post("/auth/register")
async def register(body: RegisterRequest, user: dict = Depends(require_instructor)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE username = %s", (body.username,))
            existing = await cur.fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")

            await cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (body.username, hash_password(body.password), body.role, datetime.utcnow())
            )
            
    return {"message": f"User '{body.username}' created with role '{body.role}'"}


# ── Meta Routes ───────────────────────────────────────────────────

@api_app.get("/meta/parameter-spec")
async def get_parameter_spec():
    """Return parameter spec — drives every frontend control dynamically."""
    return PARAMETER_SPEC


# ── Session Routes ────────────────────────────────────────────────

def _generate_code(length=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@api_app.post("/session/create")
async def create_session(user: dict = Depends(require_instructor)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT session_code FROM sessions WHERE created_by = %s AND is_active = 1",
                (user["id"],)
            )
            existing = await cur.fetchone()
            if existing:
                return {
                    "session_code": existing["session_code"],
                    "message": "Existing active session returned",
                }

            code = _generate_code()
            event_log = json.dumps([{"timestamp": datetime.utcnow().isoformat(), "event": "Session created"}])
            history = json.dumps([])
            
            await cur.execute(
                """INSERT INTO sessions 
                   (session_code, created_by, started_at, is_active, event_log, history) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (code, user["id"], datetime.utcnow(), True, event_log, history)
            )
            session_id = cur.lastrowid

            state = dict(DEFAULT_MONITOR_STATE)
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = user["username"]
            
            await cur.execute(
                "INSERT INTO monitor_state (session_id, state_data) VALUES (%s, %s)",
                (session_id, json.dumps(state))
            )

    return {"session_code": code, "message": "New session created"}


@api_app.get("/session/{session_code}/state")
async def get_session_state(session_code: str, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            if not state_row:
                raise HTTPException(status_code=404, detail="Monitor state not found")

    state = json.loads(state_row["state_data"])
    state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
    return state


@api_app.get("/session/{session_code}/log")
async def get_session_log(session_code: str, user: dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
    event_log = json.loads(session["event_log"]) if session["event_log"] else []
    return {"event_log": event_log}


@api_app.get("/session/{session_code}/history")
async def get_session_history(
    session_code: str,
    since: str = Query(None),
    limit: int = Query(300),
    user: dict = Depends(get_current_user),
):
    """Return numeric vital history for trend graphing."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT history FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    history = json.loads(session["history"]) if session["history"] else []
    if since:
        history = [h for h in history if h.get("timestamp", "") > since]
    return {"history": history[-limit:]}


# ── Debrief Pipeline Integration ──────────────────────────────────
DEBRIEF_STATUS_CACHE: dict = {}

async def _run_background_debrief(session_code: str):
    print(f"[BACKGROUND DEBRIEF] Starting debrief generation for session: {session_code}")
    DEBRIEF_STATUS_CACHE[session_code] = "running"
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM sessions WHERE session_code = %s", (session_code,))
                session = await cur.fetchone()
                if not session:
                    print(f"[BACKGROUND DEBRIEF] Session '{session_code}' not found")
                    DEBRIEF_STATUS_CACHE[session_code] = "failed"
                    return

                await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
                state_row = await cur.fetchone()
                monitor_state = json.loads(state_row["state_data"]) if state_row else {}

        import asyncio
        from debrief_adapter import convert_and_debrief

        loop = asyncio.get_running_loop()
        raw_log = json.loads(session["event_log"]) if session.get("event_log") else []

        result = await loop.run_in_executor(
            None,
            convert_and_debrief,
            session,
            raw_log,
            monitor_state
        )
        DEBRIEF_STATUS_CACHE[session_code] = "completed"
        print(f"[BACKGROUND DEBRIEF] Successfully completed debrief for {session_code}. Score: {result.get('overall_score')}")
    except Exception as e:
        DEBRIEF_STATUS_CACHE[session_code] = "failed"
        print(f"[BACKGROUND DEBRIEF] Error running debrief for session {session_code}: {e}")


@api_app.post("/session/{session_code}/end")
async def end_session(
    session_code: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_instructor)
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            await cur.execute(
                "UPDATE sessions SET is_active = 0, ended_at = %s WHERE id = %s",
                (datetime.utcnow(), session["id"])
            )

    # Emit session_ended to all connected clients
    await emit_session_ended(session_code)

    # Trigger background debrief generation asynchronously
    DEBRIEF_STATUS_CACHE[session_code] = "running"
    background_tasks.add_task(_run_background_debrief, session_code)

    return {"message": "Session ended", "debrief_status": "running"}


# ── Debrief API Endpoints ──────────────────────────────────────────

@api_app.post("/api/debrief/generate/{session_code}")
async def generate_debrief_endpoint(
    session_code: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Manually trigger background debrief generation for a session."""
    DEBRIEF_STATUS_CACHE[session_code] = "running"
    background_tasks.add_task(_run_background_debrief, session_code)
    return {
        "session_code": session_code,
        "status": "running",
        "message": "Debrief generation launched in background"
    }


@api_app.get("/api/debrief/status/{session_code}")
async def get_debrief_status(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Return status: pending | running | completed | failed."""
    if session_code in DEBRIEF_STATUS_CACHE:
        return {
            "session_code": session_code,
            "status": DEBRIEF_STATUS_CACHE[session_code]
        }

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT status FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if row:
                status = str(row["status"]).lower()
                return {"session_code": session_code, "status": status}

            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if session:
                return {"session_code": session_code, "status": "pending"}

    return {"session_code": session_code, "status": "pending"}


@api_app.get("/api/debrief/{session_code}")
async def get_debrief_report(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Return full debrief report object."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if not row:
                status = DEBRIEF_STATUS_CACHE.get(session_code, "pending")
                if status in ("running", "pending"):
                    return {
                        "session_code": session_code,
                        "status": status,
                        "message": "Debrief report is currently being generated"
                    }
                raise HTTPException(status_code=404, detail=f"Debrief report for '{session_code}' not found")

    debrief_data = json.loads(row["debrief_data"]) if row.get("debrief_data") else {}
    return {
        "session_code": session_code,
        "overall_score": row["overall_score"],
        "grade": row["grade"],
        "status": row["status"],
        "pdf_path": row["pdf_path"],
        "error_message": row.get("error_message"),
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"]),
        "debrief": debrief_data,
    }


@api_app.get("/api/reports/{session_code}")
async def get_report_pdf(
    session_code: str,
    user: dict = Depends(get_current_user),
):
    """Stream generated PDF report."""
    pdf_path = None
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT pdf_path FROM debrief_reports WHERE session_code = %s", (session_code,))
            row = await cur.fetchone()
            if row and row.get("pdf_path"):
                pdf_path = Path(row["pdf_path"])

    if not pdf_path or not pdf_path.exists():
        fallback = Path(__file__).parent / "debriefing" / "output" / "reports" / f"{session_code}_debrief.pdf"
        if fallback.exists():
            pdf_path = fallback

    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF report for session '{session_code}' not found or not generated yet")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{session_code}_debrief.pdf"
    )


# ── WebSocket (SimMan ECG Engine) ─────────────────────────────────

def _state_snapshot() -> str:
    """Return current engine state as a JSON STATE_SNAPSHOT string."""
    return json.dumps({
        "type": "STATE_SNAPSHOT",
        "payload": engine.state.model_dump(mode="json"),
    })

@api_app.websocket("/ws/ecg")
async def ws_ecg(websocket: WebSocket):
    await websocket.accept()
    print(f"[WS] Client connected: {websocket.client}")

    async def send_fn(data: bytes) -> None:
        await websocket.send_bytes(data)

    engine.add_client(send_fn)
    await websocket.send_text(_state_snapshot())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"[WS] Bad JSON from client: {e}")
                continue

            msg_type = msg.get("type")

            if msg_type == "SET_STATE":
                payload = msg.get("payload", {})
                try:
                    update = ECGStateUpdate.model_validate(payload)
                except Exception as e:
                    print(f"[WS] SET_STATE validation error: {e}")
                    await websocket.send_text(json.dumps({"type": "ERROR", "message": f"Validation error: {e}"}))
                    continue

                try:
                    await engine.apply_command(update)
                except Exception as e:
                    print(f"[WS] apply_command error: {e}")
                    traceback.print_exc()
                    continue

                await websocket.send_text(_state_snapshot())
                
                await websocket.send_text(json.dumps({
                    "type": "ECG_INTELLIGENCE",
                    "payload": intelligence_payload(engine.state.rhythm),
                }))

            elif msg_type == "GET_STATE":
                await websocket.send_text(_state_snapshot())
            elif msg_type == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
            else:
                print(f"[WS] Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"[WS] Unexpected crash: {e}")
        traceback.print_exc()
    finally:
        engine.remove_client(send_fn)


# ── Mount Socket.IO onto ASGI ─────────────────────────────────────

app = socketio.ASGIApp(sio, other_asgi_app=api_app)
