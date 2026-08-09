"""FastAPI app + Socket.IO mount -- main entry point."""

import random
import string
import json
import traceback
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import socketio
import aiomysql
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    require_authenticated_user,
    require_instructor,
    require_student,
)
from database import (
    init_db,
    get_db_pool
)
from models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ── Auth Routes ───────────────────────────────────────────────────

@api_app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE username = %s", (body.username,))
            user = await cur.fetchone()

    # Generic error message to prevent username enumeration
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username, password, or role.")

    # Validate requested role matches authenticated user's actual database role
    if body.role and user["role"] != body.role:
        raise HTTPException(status_code=401, detail="Invalid username, password, or role.")

    expires_delta = timedelta(days=7) if body.remember_me else timedelta(hours=24)

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "id": user["id"],
    }, expires_delta=expires_delta)

    # Set secure HttpOnly cookie for production session security
    max_age_seconds = int(expires_delta.total_seconds())
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=max_age_seconds,
        path="/",
    )

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
        user=UserResponse(id=user["id"], username=user["username"], role=user["role"]),
        session_code=session_code,
    )


@api_app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out successfully"}


@api_app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
    }


@api_app.post("/auth/register")
async def register(body: RegisterRequest):
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
        
    role = body.role if body.role in ("instructor", "student") else "student"
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE username = %s", (body.username,))
            existing = await cur.fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")

            await cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (body.username, hash_password(body.password), role, datetime.utcnow())
            )
            await conn.commit()
            
    return {"message": f"User '{body.username}' registered successfully with role '{role}'"}




# ── Meta Routes ───────────────────────────────────────────────────

@api_app.get("/meta/parameter-spec")
async def get_parameter_spec():
    """Return parameter spec — drives every frontend control dynamically."""
    return PARAMETER_SPEC


# ── Session Routes ────────────────────────────────────────────────

def _generate_code(length=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@api_app.post("/session/create")
async def create_session(body: Optional[dict] = None, user: dict = Depends(require_instructor)):
    force_new = body.get("force_new", False) if body else False
    spec = body.get("spec") if body else None

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if not force_new and not spec:
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
            scenario_json = json.dumps(spec) if spec else None
            
            await cur.execute(
                """INSERT INTO sessions 
                   (session_code, created_by, started_at, is_active, event_log, history, current_scenario_json) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (code, user["id"], datetime.utcnow(), True, event_log, history, scenario_json)
            )
            session_id = cur.lastrowid

            state = dict(DEFAULT_MONITOR_STATE)
            if spec:
                vitals = parse_scenario_spec_to_vitals(spec)
                for k, v in vitals.items():
                    state[k] = v
                state["initial_readings_hidden"] = False

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


# ── Scenario Studio Integration & API Endpoints ────────────────────

import sys
import os
import uuid
from pathlib import Path

# Add debriefing to sys.path if not present
DEBRIEFING_PATH = Path(__file__).resolve().parent / "debriefing"
if str(DEBRIEFING_PATH) not in sys.path:
    sys.path.insert(0, str(DEBRIEFING_PATH))

try:
    from scenarios.generator import ScenarioGenerator
    from scenarios.outcome_predictor import OutcomePredictor
    from scenarios.voice_narrator import VoiceNarrator
    from scenarios.instructor_listener import InstructorListener
    
    _scenario_gen = ScenarioGenerator()
    _outcome_pred = OutcomePredictor()
    _narrator = VoiceNarrator(output_dir=DEBRIEFING_PATH / "output" / "tts")
    _instructor = InstructorListener()
except Exception as e:
    print(f"[main.py] Warning: Scenario modules failed to load: {e}")
    _scenario_gen = _outcome_pred = _narrator = _instructor = None

_active_scenario_runs = {}

def map_rhythm_type_to_vitals(rhythm_type: str) -> dict:
    rt = (rhythm_type or "").upper()
    if "VF" in rt or "FIBRILLATION" in rt:
        return {
            "rhythm": "Ventricular Fibrillation",
            "HR": 0.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": False,
        }
    elif "PEA" in rt:
        return {
            "rhythm": "Sinus Rhythm",
            "HR": 60.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": True,
        }
    elif "ASYSTOLE" in rt:
        return {
            "rhythm": "Asystole",
            "HR": 0.0,
            "pulse_rate": 0.0,
            "SpO2": 0.0,
            "ABP_sys": 0.0,
            "ABP_dia": 0.0,
            "MAP": 0.0,
            "avRR": 0.0,
            "etCO2": 0.0,
            "emd_pea": False,
        }
    elif "BRADY" in rt:
        return {
            "rhythm": "Sinus Bradycardia",
            "HR": 40.0,
            "pulse_rate": 40.0,
            "SpO2": 92.0,
            "ABP_sys": 90.0,
            "ABP_dia": 60.0,
            "MAP": 70.0,
            "avRR": 10.0,
            "etCO2": 35.0,
            "emd_pea": False,
        }
    elif "TACHY" in rt or "SVT" in rt:
        return {
            "rhythm": "SVT",
            "HR": 150.0,
            "pulse_rate": 150.0,
            "SpO2": 95.0,
            "ABP_sys": 100.0,
            "ABP_dia": 70.0,
            "MAP": 80.0,
            "avRR": 20.0,
            "etCO2": 38.0,
            "emd_pea": False,
        }
    else:
        return {
            "rhythm": "Sinus Rhythm",
            "HR": 75.0,
            "pulse_rate": 75.0,
            "SpO2": 98.0,
            "ABP_sys": 120.0,
            "ABP_dia": 80.0,
            "MAP": 93.0,
            "avRR": 14.0,
            "etCO2": 35.0,
            "emd_pea": False,
        }

@api_app.get("/api/scenario/list")
async def api_scenario_list(user: dict = Depends(get_current_user)):
    if not _scenario_gen:
        raise HTTPException(status_code=503, detail="Scenario generator not available")
    return {
        "levels": _scenario_gen.list_levels(),
        "locations": _scenario_gen.list_locations(),
        "specialities": _scenario_gen.list_specialities(),
        "disciplines": {
            "doctor": "Physician / Registrar",
            "nurse": "Staff Nurse / Charge Nurse",
            "physiotherapist": "Physiotherapist",
            "allied": "Allied Health Professional",
        },
    }

@api_app.post("/api/scenario/generate")
async def api_scenario_generate(body: dict, user: dict = Depends(get_current_user)):
    if not _scenario_gen:
        raise HTTPException(status_code=503, detail="Scenario generator not available")
    level = body.get("level", "beginner")
    location = body.get("location", "ER")
    discipline = body.get("discipline", ["doctor"])
    speciality = body.get("speciality", "ER")
    
    spec = _scenario_gen.generate(
        level=level, location=location,
        discipline=discipline, speciality=speciality,
    )
    expected = None
    if _outcome_pred:
        expected = _outcome_pred.build_expected(spec)
        
    return {"spec": spec, "expected_outcome": expected}

def parse_scenario_spec_to_vitals(spec: dict) -> dict:
    rhythm_type = spec.get("rhythm_type") or spec.get("rhythm") or "Sinus Rhythm"
    vitals = map_rhythm_type_to_vitals(rhythm_type)
    
    raw_vitals = spec.get("initial_vitals") or spec.get("vitals") or spec.get("initial_readings") or {}
    if not isinstance(raw_vitals, dict):
        raw_vitals = {}

    def get_val(keys):
        for k in keys:
            if k in raw_vitals and raw_vitals[k] is not None:
                return raw_vitals[k]
            if k in spec and spec[k] is not None:
                return spec[k]
        return None

    # Rhythm
    rhythm_val = get_val(["rhythm", "rhythm_type", "ecgRhythm"])
    if rhythm_val:
        vitals["rhythm"] = str(rhythm_val)

    # Heart rate
    hr_val = get_val(["heart_rate", "heartRate", "HR", "hr"])
    if hr_val is not None:
        try:
            val = float(hr_val)
            vitals["HR"] = val
            vitals["pulse_rate"] = val
        except (ValueError, TypeError):
            pass

    # SpO2
    spo2_val = get_val(["spo2", "SpO2", "SPO2"])
    if spo2_val is not None:
        try:
            vitals["SpO2"] = float(spo2_val)
        except (ValueError, TypeError):
            pass

    # Blood Pressure
    bp_sys = get_val(["sys_bp", "systolic_bp", "ABP_sys", "sysBP", "systolic"])
    bp_dia = get_val(["dia_bp", "diastolic_bp", "ABP_dia", "diaBP", "diastolic"])
    
    bp_obj = get_val(["bloodPressure", "blood_pressure"])
    if isinstance(bp_obj, dict):
        bp_sys = bp_sys or bp_obj.get("systolic") or bp_obj.get("sys")
        bp_dia = bp_dia or bp_obj.get("diastolic") or bp_obj.get("dia")
        
    if bp_sys is not None:
        try:
            v = float(bp_sys)
            vitals["ABP_sys"] = v
            vitals["NBP_sys"] = v
        except (ValueError, TypeError):
            pass

    if bp_dia is not None:
        try:
            v = float(bp_dia)
            vitals["ABP_dia"] = v
            vitals["NBP_dia"] = v
        except (ValueError, TypeError):
            pass

    if "ABP_sys" in vitals and "ABP_dia" in vitals and vitals["ABP_sys"] > 0:
        map_val = round((vitals["ABP_sys"] + 2 * vitals["ABP_dia"]) / 3.0, 1)
        vitals["MAP"] = map_val
        vitals["NBP_mean"] = map_val

    # Respiratory Rate
    rr_val = get_val(["resp_rate", "respiratory_rate", "respiratoryRate", "avRR", "RR", "rr"])
    if rr_val is not None:
        try:
            vitals["avRR"] = float(rr_val)
        except (ValueError, TypeError):
            pass

    # EtCO2
    etco2_val = get_val(["etco2", "etCO2", "ETCO2"])
    if etco2_val is not None:
        try:
            vitals["etCO2"] = float(etco2_val)
        except (ValueError, TypeError):
            pass

    # Temperature
    temp_val = get_val(["temperature", "Tblood", "temp", "blood_temperature"])
    if isinstance(temp_val, dict):
        temp_val = temp_val.get("bloodTemperature") or temp_val.get("blood") or temp_val.get("value")
    if temp_val is not None:
        try:
            v = float(temp_val)
            vitals["Tblood"] = v
            vitals["Tperi"] = round(v - 0.5, 1)
        except (ValueError, TypeError):
            pass

    # Cardiac Output
    co_val = get_val(["cardiac_output", "cardiacOutput", "CO"])
    if co_val is not None:
        try:
            vitals["CO"] = float(co_val)
        except (ValueError, TypeError):
            pass

    # PAP
    pap_sys = get_val(["pap_sys", "PAP_sys"])
    pap_dia = get_val(["pap_dia", "PAP_dia"])
    pap_obj = get_val(["pulmonaryArteryPressure", "pap"])
    if isinstance(pap_obj, dict):
        pap_sys = pap_sys or pap_obj.get("systolic")
        pap_dia = pap_dia or pap_obj.get("diastolic")

    if pap_sys is not None:
        try:
            vitals["PAP_sys"] = float(pap_sys)
        except (ValueError, TypeError):
            pass
    if pap_dia is not None:
        try:
            vitals["PAP_dia"] = float(pap_dia)
        except (ValueError, TypeError):
            pass

    return vitals

@api_app.post("/api/scenario/start")
async def api_scenario_start(body: dict, user: dict = Depends(get_current_user)):
    spec = body.get("spec", {})
    session_code = body.get("session_code")
    
    run_id = str(uuid.uuid4())
    _active_scenario_runs[run_id] = {
        "spec": spec,
        "started_at": datetime.utcnow().isoformat(),
        "status": "active"
    }
    
    if session_code:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
                session = await cur.fetchone()
                if session:
                    # Update sessions table with the scenario spec JSON
                    await cur.execute(
                        "UPDATE sessions SET current_scenario_json = %s, current_scenario_id = NULL WHERE id = %s",
                        (json.dumps(spec), session["id"])
                    )
                    
                    # Parse vitals from spec
                    vitals = parse_scenario_spec_to_vitals(spec)
                    
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
                    state_row = await cur.fetchone()
                    if state_row:
                        state = json.loads(state_row["state_data"])
                        for k, v in vitals.items():
                            state[k] = v
                        state["initial_readings_hidden"] = False
                        state["last_updated"] = datetime.utcnow().isoformat()
                        state["updated_by"] = user.get("username", "")
                        
                        from socket_manager import sio, compute_alarms
                        state["alarms"] = compute_alarms(state)
                        
                        await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
                        
                        # Apply initial scenario state to SimMan ECG Engine state machine
                        try:
                            from simman_engine.state_machine import engine
                            from ecg_state import ECGStateUpdate
                            engine_update = {}
                            if "HR" in state: engine_update["heart_rate"] = state["HR"]
                            if "rhythm" in state: engine_update["rhythm"] = state["rhythm"]
                            if "ABP_sys" in state: engine_update["sys_bp"] = state["ABP_sys"]
                            if "ABP_dia" in state: engine_update["dia_bp"] = state["ABP_dia"]
                            if "SpO2" in state: engine_update["spo2"] = state["SpO2"]
                            if "avRR" in state: engine_update["resp_rate"] = state["avRR"]
                            if "etCO2" in state: engine_update["etco2"] = state["etCO2"]
                            if "PAP_sys" in state: engine_update["pap_sys"] = state["PAP_sys"]
                            if "PAP_dia" in state: engine_update["pap_dia"] = state["PAP_dia"]
                            
                            if engine_update:
                                await engine.apply_command(ECGStateUpdate.model_validate(engine_update))
                        except Exception as e:
                            print(f"[api_scenario_start] Engine sync warning: {e}")

                        # Emit updates to SIO room

                        await sio.emit("state_update", state, room=session_code)
                        await sio.emit("rhythm_change", {
                            k: state.get(k) for k in
                            ["rhythm", "extrasystole", "HR", "ecg_lead",
                             "artifact_electrical", "artifact_muscular", "emd_pea"]
                        }, room=session_code)
                        
                        # Broadcast scenario_selected
                        await sio.emit("scenario_selected", spec, room=session_code)
                        
    return {"run_id": run_id, "status": "active"}

@api_app.post("/api/scenario/speak")
async def api_scenario_speak(body: dict, user: dict = Depends(get_current_user)):
    if not _narrator:
         raise HTTPException(status_code=503, detail="Voice narrator not available")
    text = body.get("text", "")
    speak_type = body.get("type", "custom")
    spec = body.get("spec")
    
    # We default to browser TTS to bypass server-side setup dependencies
    if speak_type == "intro" and spec:
        text = spec.get("narration_intro", "")
    
    return {"mode": "browser", "text": text}

@api_app.post("/api/scenario/narrate")
async def api_scenario_narrate(body: dict, user: dict = Depends(get_current_user)):
    spec = body.get("spec", {})
    text = spec.get("narration_intro", "")
    if not text:
        pt = spec.get("patient", {})
        text = (
            f"Attention team. {spec.get('level','').title()}-level scenario "
            f"in the {spec.get('location_label', 'hospital')}. "
            f"Patient: {pt.get('age','?')}-year-old {pt.get('sex','patient')}. "
            f"Presentation: {pt.get('presentation','cardiac arrest')}. You may begin."
        )
    return {"mode": "browser", "text": text}

@api_app.post("/api/scenario/instructor")
async def api_scenario_instructor(body: dict, user: dict = Depends(get_current_user)):
    if not _instructor:
         raise HTTPException(status_code=503, detail="Instructor listener not available")
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
        
    params = _instructor.parse_text(text)
    params.setdefault("level", "beginner")
    params.setdefault("location", "ER")
    params.setdefault("speciality", "ER")
    params.setdefault("discipline", ["doctor"])
    
    spec = {}
    if _scenario_gen:
        spec = _scenario_gen.generate(
            level=params["level"],
            location=params["location"],
            discipline=params["discipline"],
            speciality=params["speciality"],
        )
    return {"parsed_params": params, "spec": spec}


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

    raw_token = websocket.query_params.get("token") or websocket.cookies.get("access_token")
    auth_user = None
    if raw_token:
        try:
            payload = decode_token(raw_token)
            auth_user = {"username": payload.get("sub"), "role": payload.get("role")}
        except Exception:
            pass

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
                if auth_user and auth_user.get("role") not in ("instructor", "operator", "admin"):
                    await websocket.send_text(json.dumps({
                        "type": "ERROR",
                        "message": "Instructor role required to update state machine"
                    }))
                    continue

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
