"""Socket.IO server and event handlers — matches frozen contract."""

import asyncio
import math
import json
from datetime import datetime

import socketio
import aiomysql
from auth import decode_token
from database import get_db_pool
from models import DEFAULT_MONITOR_STATE

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Track active transfer tasks: { (session_id, field): asyncio.Task }
_transfer_tasks: dict = {}

# Scenarios Cache
SCENARIOS_CACHE = []
_active_nibp_loops = {}

async def _run_nibp_measurement(session_id, session_code):
    try:
        pool = await get_db_pool()
        stages = [
            ("INFLATING", 2.5),
            ("MEASURING", 3.0),
            ("PROCESSING", 2.0)
        ]
        
        for state_name, duration in stages:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                    state_row = await cur.fetchone()
                    if not state_row:
                        return
                    state = json.loads(state_row["state_data"])
                    state["nibp_state"] = state_name
                    await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session_id))
            
            await sio.emit("state_update", state, room=session_code)
            await asyncio.sleep(duration)
            
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                state_row = await cur.fetchone()
                if not state_row:
                    return
                state = json.loads(state_row["state_data"])
                
                target_sys = state.get("nbp_target_sys", state.get("NBP_sys", 120.0))
                target_dia = state.get("nbp_target_dia", state.get("NBP_dia", 80.0))
                
                state["NBP_sys"] = target_sys
                state["NBP_dia"] = target_dia
                state["NBP_mean"] = round(target_dia + (target_sys - target_dia) / 3.0, 1)
                state["nibp_state"] = "COMPLETE"
                state["nibp_last_measured"] = datetime.utcnow().isoformat()
                
                await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session_id))
                
        await sio.emit("state_update", state, room=session_code)
    except Exception as e:
        print(f"[NIBP Measurement Error] {e}")

async def _nibp_interval_loop(session_id, session_code):
    while True:
        try:
            await asyncio.sleep(10)
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                    state_row = await cur.fetchone()
                    if not state_row:
                        break
                    state = json.loads(state_row["state_data"])
                    
            interval = int(state.get("nibp_interval", 0))
            nibp_state = state.get("nibp_state", "IDLE")
            
            if interval > 0 and nibp_state in ("IDLE", "COMPLETE"):
                last_measured_str = state.get("nibp_last_measured", "")
                should_measure = False
                if not last_measured_str:
                    should_measure = True
                else:
                    try:
                        last_measured = datetime.fromisoformat(last_measured_str)
                        elapsed_minutes = (datetime.utcnow() - last_measured).total_seconds() / 60.0
                        if elapsed_minutes >= interval:
                            should_measure = True
                    except Exception:
                        should_measure = True
                        
                if should_measure:
                    asyncio.create_task(_run_nibp_measurement(session_id, session_code))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[NIBP Loop Error] {e}")
            await asyncio.sleep(5)


def safe_parse_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val

async def load_scenarios_to_cache():
    global SCENARIOS_CACHE
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, name, patient_details, symptoms, initial_readings FROM scenarios")
            rows = await cur.fetchall()
            SCENARIOS_CACHE = []
            for r in rows:
                SCENARIOS_CACHE.append({
                    "id": r["id"],
                    "name": r["name"],
                    "patient_details": safe_parse_json(r["patient_details"]),
                    "symptoms": safe_parse_json(r["symptoms"]),
                    "initial_readings": safe_parse_json(r["initial_readings"])
                })
            print(f"[CACHE] Loaded {len(SCENARIOS_CACHE)} scenarios into memory cache.")

def map_scenario_to_state(monitor_values):
    state_updates = {}
    if not isinstance(monitor_values, dict):
        return state_updates

    if "heartRate" in monitor_values and monitor_values["heartRate"] is not None:
        try:
            val = float(monitor_values["heartRate"])
            state_updates["HR"] = val
            state_updates["pulse_rate"] = val
        except (ValueError, TypeError):
            pass

    if "spo2" in monitor_values and monitor_values["spo2"] is not None:
        try:
            state_updates["SpO2"] = float(monitor_values["spo2"])
        except (ValueError, TypeError):
            pass

    sys_v, dia_v = None, None
    if "bloodPressure" in monitor_values:
        bp = monitor_values["bloodPressure"]
        if isinstance(bp, dict):
            sys_v = bp.get("systolic")
            dia_v = bp.get("diastolic")
        elif isinstance(bp, str) and "/" in bp:
            try:
                parts = bp.split("(")[0].strip().split("/")
                sys_v = float(parts[0])
                dia_v = float(parts[1])
            except Exception:
                pass
    if sys_v is None and "systolicBp" in monitor_values:
        sys_v = monitor_values.get("systolicBp")
    if dia_v is None and "diastolicBp" in monitor_values:
        dia_v = monitor_values.get("diastolicBp")

    if sys_v is not None:
        try:
            sys_num = float(sys_v)
            state_updates["ABP_sys"] = sys_num
            state_updates["NBP_sys"] = sys_num
        except (ValueError, TypeError):
            pass

    if dia_v is not None:
        try:
            dia_num = float(dia_v)
            state_updates["ABP_dia"] = dia_num
            state_updates["NBP_dia"] = dia_num
        except (ValueError, TypeError):
            pass

    if "ABP_sys" in state_updates and "ABP_dia" in state_updates and state_updates["ABP_sys"] > 0:
        map_val = round((state_updates["ABP_sys"] + 2 * state_updates["ABP_dia"]) / 3.0, 1)
        state_updates["MAP"] = map_val
        state_updates["NBP_mean"] = map_val

    if "respiratoryRate" in monitor_values and monitor_values["respiratoryRate"] is not None:
        try:
            state_updates["avRR"] = float(monitor_values["respiratoryRate"])
        except (ValueError, TypeError):
            pass

    if "temperature" in monitor_values and monitor_values["temperature"] is not None:
        temp = monitor_values["temperature"]
        if isinstance(temp, dict):
            try:
                t_val = float(temp.get("bloodTemperature", 37.0))
                state_updates["Tblood"] = t_val
                state_updates["Tperi"] = float(temp.get("peripheralTemperature", t_val - 0.5))
            except (ValueError, TypeError):
                pass
        elif isinstance(temp, (int, float)):
            t_val = float(temp)
            state_updates["Tblood"] = t_val
            state_updates["Tperi"] = round(t_val - 0.5, 1)
        elif isinstance(temp, str):
            try:
                t_val = float(temp.replace("°C", "").replace("C", "").strip())
                state_updates["Tblood"] = t_val
                state_updates["Tperi"] = round(t_val - 0.5, 1)
            except Exception:
                pass

    if "cardiacOutput" in monitor_values and monitor_values["cardiacOutput"] is not None:
        try:
            state_updates["CO"] = float(monitor_values["cardiacOutput"])
        except (ValueError, TypeError):
            pass

    if "pulmonaryArteryPressure" in monitor_values:
        pap = monitor_values["pulmonaryArteryPressure"]
        if isinstance(pap, dict):
            try:
                state_updates["PAP_sys"] = float(pap.get("systolic", 20.0))
                state_updates["PAP_dia"] = float(pap.get("diastolic", 10.0))
                state_updates["PAP_mean"] = float(pap.get("mean", 13.0))
            except (ValueError, TypeError):
                pass

    if "pulmonaryCapillaryWedgePressure" in monitor_values and monitor_values["pulmonaryCapillaryWedgePressure"] is not None:
        try:
            state_updates["PAP_wedge"] = float(monitor_values["pulmonaryCapillaryWedgePressure"])
        except (ValueError, TypeError):
            pass

    if "etco2" in monitor_values and monitor_values["etco2"] is not None:
        try:
            state_updates["etCO2"] = float(monitor_values["etco2"])
        except (ValueError, TypeError):
            pass

    if "ecgRhythm" in monitor_values and monitor_values["ecgRhythm"]:
        state_updates["rhythm"] = str(monitor_values["ecgRhythm"])

    return state_updates


async def emit_scenario_selected(session_code, scenario):
    student_scenario = dict(scenario)
    student_scenario.pop("initial_readings", None)
    
    sids = []
    try:
        room_data = sio.manager.rooms.get("/", {}).get(session_code, {})
        sids = list(room_data.keys())
    except Exception:
        try:
            participants = sio.manager.get_participants("/", session_code)
            sids = [p[0] if isinstance(p, tuple) else p for p in participants]
        except Exception:
            pass
            
    if not sids:
        await sio.emit("scenario_selected", student_scenario, room=session_code)
        return

    for sid in sids:
        try:
            client_session = await sio.get_session(sid)
            if client_session and client_session.get("role") == "instructor":
                await sio.emit("scenario_selected", scenario, to=sid)
            else:
                await sio.emit("scenario_selected", student_scenario, to=sid)
        except Exception:
            pass


def compute_alarms(state: dict) -> list[str]:
    """Compute alarms by checking values against alarm_thresholds."""
    alarms = []
    thresholds = state.get("alarm_thresholds", {})

    for field, bounds in thresholds.items():
        val = state.get(field)
        if val is None:
            continue
        low = bounds.get("low")
        high = bounds.get("high")
        if low is not None and val < low:
            alarms.append(f"{field} LOW")
        if high is not None and val > high:
            alarms.append(f"{field} HIGH")

    # Special named alarms
    if state.get("avRR", 14) == 0:
        alarms.append("APNEA")
    if state.get("SpO2", 98) < 90:
        alarms.append("DESAT")

    return alarms


# ── Socket Events ─────────────────────────────────────────────────

@sio.event
async def connect(sid, environ):
    print(f"[SIO] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[SIO] Client disconnected: {sid}")


@sio.event
async def join_session(sid, data):
    """Client joins a session room."""
    environ = sio.environ.get(sid, {}) if hasattr(sio, 'environ') else {}
    session_code = data.get("session_code") if isinstance(data, dict) else None
    token = data.get("token") if isinstance(data, dict) else None

    if not token and environ and "HTTP_COOKIE" in environ:
        try:
            from http.cookies import SimpleCookie
            cookie = SimpleCookie(environ.get("HTTP_COOKIE"))
            if "access_token" in cookie:
                token = cookie["access_token"].value
        except Exception:
            pass

    if not session_code or not token or token in ("demo-token", "", "null", "undefined"):
        await sio.emit("error", {"message": "Missing or invalid token"}, to=sid)
        return

    try:
        payload = decode_token(token)
    except Exception:
        await sio.emit("error", {"message": "Invalid or expired token"}, to=sid)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            
            if not session:
                await sio.emit("error", {"message": "Session not found"}, to=sid)
                return

            await sio.enter_room(sid, session_code)
            await sio.save_session(sid, {
                "username": payload.get("sub"),
                "role": payload.get("role"),
                "session_code": session_code,
            })

            # Confirm join to the client (frontend listens for this)
            await sio.emit("join_confirmed", {
                "session_code": session_code,
                "role": payload.get("role"),
            }, to=sid)

            # Send current state with started_at
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            
            if state_row:
                state = json.loads(state_row["state_data"])
                state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
                await sio.emit("state_update", state, to=sid)
            # Send current event log history to the client
            await cur.execute("SELECT event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_event_row = await cur.fetchone()
            if sess_event_row and sess_event_row.get("event_log"):
                event_history = json.loads(sess_event_row["event_log"])
                await sio.emit("session_history_log", {"event_log": event_history}, to=sid)

            # If session has current_scenario_id or current_scenario_json, fetch and send it
            await cur.execute("SELECT current_scenario_id, current_scenario_json FROM sessions WHERE id = %s", (session["id"],))
            session_row = await cur.fetchone()
            if session_row:
                scenario = None
                if session_row.get("current_scenario_json"):
                    try:
                        scenario = json.loads(session_row["current_scenario_json"])
                    except Exception:
                        pass
                elif session_row.get("current_scenario_id"):
                    scenario_id = session_row["current_scenario_id"]
                    scenario = next((s for s in SCENARIOS_CACHE if s["id"] == scenario_id), None)
                
                if scenario:
                    if payload.get("role") == "instructor":
                        await sio.emit("scenario_selected", scenario, to=sid)
                    else:
                        student_scenario = dict(scenario)
                        student_scenario.pop("initial_readings", None)
                        await sio.emit("scenario_selected", student_scenario, to=sid)

            if payload.get("role") == "instructor":
                session_id = session["id"]
                if session_id not in _active_nibp_loops:
                    _active_nibp_loops[session_id] = asyncio.create_task(_nibp_interval_loop(session_id, session_code))

    print(f"[SIO] {payload.get('sub')} joined session {session_code}")


@sio.event
async def update_parameter(sid, data):
    """Instructor updates a single parameter.
    Contract: {field, value, transfer_time_seconds, transfer_function}
    """
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    field = data.get("field")
    value = data.get("value")
    transfer_seconds = data.get("transfer_time_seconds", 0)
    transfer_fn = data.get("transfer_function", "immediate")

    if not field:
        await sio.emit("error", {"message": "Missing field"}, to=sid)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

    if transfer_seconds and transfer_seconds > 0 and transfer_fn in ("linear", "smooth"):
        print(f"[TRANSFER] Starting {transfer_fn} transfer: {field} -> {value} over {transfer_seconds}s")
        await _start_transfer(
            session, session_code, field, value,
            transfer_seconds, transfer_fn, session_data.get("username", "")
        )
    else:
        print(f"[UPDATE] Instant: {field} -> {value}")
        await _apply_update(session, session_code, field, value, session_data.get("username", ""))


@sio.event
async def update_rhythm(sid, data):
    """Instructor updates cardiac rhythm settings."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            update_fields = {}
            for key in ["rhythm", "extrasystole", "HR", "ecg_lead",
                        "artifact_electrical", "artifact_muscular", "emd_pea"]:
                if key in data:
                    update_fields[key] = data[key]

            # Keep pulse_rate in sync with HR
            if "HR" in update_fields:
                update_fields["pulse_rate"] = update_fields["HR"]

            update_fields["last_updated"] = datetime.utcnow().isoformat()
            update_fields["updated_by"] = session_data.get("username", "")

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            for k, v in update_fields.items():
                state[k] = v
                
            state["initial_readings_hidden"] = False
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Rhythm -> {state.get('rhythm')}, HR -> {state.get('HR')}",
            }
            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
            
    await sio.emit("state_update", state, room=session_code)
    await sio.emit("rhythm_change", {
        k: state.get(k) for k in
        ["rhythm", "extrasystole", "HR", "ecg_lead",
         "artifact_electrical", "artifact_muscular", "emd_pea"]
    }, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)


@sio.event
async def update_eyes(sid, data):
    """Instructor updates eyes state."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            update_fields = {}
            if "eyes_state" in data:
                update_fields["eyes_state"] = data["eyes_state"]
            if "eyes_look" in data:
                update_fields["eyes_look"] = data["eyes_look"]

            update_fields["last_updated"] = datetime.utcnow().isoformat()
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            for k, v in update_fields.items():
                state[k] = v
                
            state["initial_readings_hidden"] = False
            state["alarms"] = compute_alarms(state)
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)


@sio.event
async def add_event_log(sid, data):
    """Add an event to the session log."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    event_text = data.get("event", "")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event_text,
            }
            event_log.append(entry)
            
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
    await sio.emit("session_event", entry, room=session_code)


@sio.event
async def faculty_comment(sid, data):
    """Broadcast instructor comment/message to the session room."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    comment_text = data.get("comment", "")
    
    entry = {
        "from": session_data.get("username", "Instructor"),
        "comment": comment_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    await sio.emit("faculty_comment", entry, room=session_code)


@sio.event
async def update_alarm_thresholds(sid, data):
    """Instructor updates alarm thresholds."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            new_thresholds = data.get("thresholds", {})
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            state["alarm_thresholds"] = new_thresholds
            state["initial_readings_hidden"] = False
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)


@sio.event
async def list_scenarios(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    await sio.emit("scenarios_list", SCENARIOS_CACHE, to=sid)


@sio.event
async def select_scenario(sid, data):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    
    session_code = session_data.get("session_code")
    scenario_id = data.get("scenario_id")
    if not scenario_id:
        await sio.emit("error", {"message": "Missing scenario_id"}, to=sid)
        return
    
    scenario = next((s for s in SCENARIOS_CACHE if s["id"] == scenario_id), None)
    if not scenario:
        await sio.emit("error", {"message": f"Scenario {scenario_id} not found"}, to=sid)
        return
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return
            
            await cur.execute("UPDATE sessions SET current_scenario_id = %s WHERE id = %s", (scenario_id, session["id"]))
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            updates = map_scenario_to_state(scenario["initial_readings"])
            for k, v in updates.items():
                state[k] = v
            
            state["initial_readings_hidden"] = True
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = session_data.get("username", "")
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Scenario loaded: {scenario['name']}",
            }
            await cur.execute("SELECT event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_row = await cur.fetchone()
            event_log = json.loads(sess_row["event_log"]) if sess_row and sess_row["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)
    await emit_scenario_selected(session_code, scenario)


@sio.event
async def request_random_scenario(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    
    if not SCENARIOS_CACHE:
        await sio.emit("error", {"message": "No scenarios loaded in cache"}, to=sid)
        return
    
    import random
    scenario = random.choice(SCENARIOS_CACHE)
    await select_scenario(sid, {"scenario_id": scenario["id"]})


@sio.event
async def apply_all_settings(sid, data):
    """Instructor commits all current settings as a single transaction."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])

            # Extract NIBP updates to target variables
            if "NBP_sys" in data:
                state["nbp_target_sys"] = data.pop("NBP_sys")
            if "NBP_dia" in data:
                state["nbp_target_dia"] = data.pop("NBP_dia")

            # Apply other settings
            for k, v in data.items():
                state[k] = v

            # Keep derived fields in sync (except NIBP which is updated on cuff finish)
            if "HR" in data:
                state["pulse_rate"] = data["HR"]
            if "ABP_sys" in data or "ABP_dia" in data:
                sys_val = state.get("ABP_sys", 120.0)
                dia_val = state.get("ABP_dia", 80.0)
                state["MAP"] = round(dia_val + (sys_val - dia_val) / 3.0, 1)
            if "PAP_sys" in data or "PAP_dia" in data:
                sys_val = state.get("PAP_sys", 20.0)
                dia_val = state.get("PAP_dia", 10.0)
                state["PAP_mean"] = round(dia_val + (sys_val - dia_val) / 3.0, 1)

            state["initial_readings_hidden"] = False
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = session_data.get("username", "")
            state["alarms"] = compute_alarms(state)

            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))

            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Applied atomic settings update",
            }
            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))

            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)

    # If rhythm/HR changed, broadcast rhythm_change
    if any(k in data for k in ["rhythm", "extrasystole", "HR", "ecg_lead", "artifact_electrical", "artifact_muscular", "emd_pea"]):
        await sio.emit("rhythm_change", {
            k: state.get(k) for k in
            ["rhythm", "extrasystole", "HR", "ecg_lead",
             "artifact_electrical", "artifact_muscular", "emd_pea"]
        }, room=session_code)

    return {"status": "success"}


@sio.event
async def measure_nibp(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    session_code = session_data.get("session_code")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            if state_row:
                state = json.loads(state_row["state_data"])
                if state.get("nibp_state") in ("INFLATING", "MEASURING", "PROCESSING"):
                    return

    asyncio.create_task(_run_nibp_measurement(session["id"], session_code))


# ── Helpers ───────────────────────────────────────────────────────

async def _apply_update(session, session_code, field, value, username):
    """Apply a single field update, recompute alarms, broadcast."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])

            state[field] = value
            state["initial_readings_hidden"] = False
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = username

            # Keep derived fields in sync
            if field == "HR":
                state["pulse_rate"] = value
            if field in ("ABP_sys", "ABP_dia"):
                sys_val = state.get("ABP_sys", 120)
                dia_val = state.get("ABP_dia", 80)
                state["MAP"] = round(dia_val + (sys_val - dia_val) / 3, 1)
            if field in ("NBP_sys", "NBP_dia"):
                sys_val = state.get("NBP_sys", 120)
                dia_val = state.get("NBP_dia", 80)
                state["NBP_mean"] = round(dia_val + (sys_val - dia_val) / 3, 1)
            if field in ("PAP_sys", "PAP_dia"):
                sys_val = state.get("PAP_sys", 20)
                dia_val = state.get("PAP_dia", 10)
                state["PAP_mean"] = round(dia_val + (sys_val - dia_val) / 3, 1)

            state["alarms"] = compute_alarms(state)
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))

            await cur.execute("SELECT started_at, event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_row = await cur.fetchone()
            
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"{field} -> {value}",
            }
            event_log = json.loads(sess_row["event_log"]) if sess_row["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
            state["started_at"] = sess_row["started_at"].isoformat() if sess_row["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)


async def _start_transfer(session, session_code, field, target_value,
                           transfer_seconds, transfer_fn, username):
    """Background interpolation: linear or smooth (ease-in-out)."""
    task_key = (str(session["id"]), field)

    if task_key in _transfer_tasks:
        _transfer_tasks[task_key].cancel()

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
    start_value = state.get(field, 0)
    steps = max(int(transfer_seconds), 1)

    async def _interpolate():
        try:
            for i in range(1, steps + 1):
                await asyncio.sleep(1)
                t = i / steps  # 0..1
                if transfer_fn == "smooth":
                    # Ease-in-out (smoothstep)
                    t = t * t * (3 - 2 * t)
                # linear is just t
                val = start_value + (target_value - start_value) * t
                val = round(val, 1)
                print(f"[TRANSFER] {field}: step {i}/{steps} = {val}")
                await _apply_update(session, session_code, field, val, username)
            # Final exact value
            await _apply_update(session, session_code, field, target_value, username)
            print(f"[TRANSFER] {field}: done -> {target_value}")
        except asyncio.CancelledError:
            print(f"[TRANSFER] {field}: cancelled")
        finally:
            _transfer_tasks.pop(task_key, None)

    task = asyncio.create_task(_interpolate())
    _transfer_tasks[task_key] = task


async def emit_session_ended(session_code: str):
    """Emit session_ended to all clients in the room."""
    await sio.emit("session_ended", {"session_code": session_code}, room=session_code)
