import json
import uuid
import hashlib
import hmac
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, List
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from warrantymind.config import (
    BASE_DIR, UPLOAD_DIR, ENVIRONMENT, SECRET_KEY, MAX_UPLOAD_BYTES, MAX_IMAGE_PIXELS,
    ALLOWED_IMAGE_TYPES, ENABLE_OLLAMA, OLLAMA_BASE_URL, VISION_MODEL, TEXT_MODEL,
    BRAVE_SEARCH_API_KEY,
)
from warrantymind.database import get_conn, seed_demo_data, verify_password, hash_password
from warrantymind.database import init_db
from warrantymind.schemas import (
    DiagnosticInterviewReplyRequest,
    SlotConsentRequest,
    TechnicianInspectionInput,
    RepairOfferConsentRequest,
    EscalationRequest,
    SupportReplyRequest,
)
from warrantymind.mcp_servers.evidence_mcp import evidence_mcp
from warrantymind.mcp_servers.diagnostic_interview_mcp import diagnostic_interview_mcp
from warrantymind.mcp_servers.policy_rag_mcp import policy_rag_mcp
from warrantymind.mcp_servers.service_ops_mcp import service_ops_mcp
from warrantymind.orchestrator.graph import orchestrator

app = FastAPI(
    title="WarrantyMind AI — Pixel Support, Ollama Reasoning, Warranty Research & Human Review",
    version="3.1.0",
)

SUPPORTED_PIXEL_CATEGORIES = {"Pixel Phone", "Pixel Watch", "Pixelbook"}


def _require_pixel_case(row: Any, conn: Any = None) -> None:
    """Prevent legacy Apple-demo records from entering the Pixel workflow."""
    if row["product_category"] not in SUPPORTED_PIXEL_CATEGORIES:
        if conn is not None:
            conn.close()
        raise HTTPException(
            status_code=410,
            detail="This is a legacy case from the previous demo catalog. Create a new Pixel support case to continue.",
        )

_SESSION_HASH_KEY = SECRET_KEY.encode("utf-8") if SECRET_KEY else hashlib.sha256(uuid.uuid4().bytes).digest()


def _session_fingerprint(token: str) -> str:
    return hmac.new(_SESSION_HASH_KEY, token.encode("utf-8"), hashlib.sha256).hexdigest()


@app.on_event("startup")
def on_startup():
    if ENVIRONMENT in {"production", "prod"}:
        if len(SECRET_KEY) < 32 or SECRET_KEY == "wm-local-dev-secret-key-change-in-prod":
            raise RuntimeError("Production requires WM_SECRET_KEY to be set to a random value of at least 32 characters")
        init_db()
    else:
        seed_demo_data()


STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    conn = get_conn()
    row = conn.execute(
        "SELECT s.token, s.username, s.role, s.created_at, u.full_name, u.service_center_id FROM sessions s JOIN users u ON s.username = u.username WHERE s.token = ?",
        (_session_fingerprint(token),),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    try:
        created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(hours=12):
            conn = get_conn()
            conn.execute("DELETE FROM sessions WHERE token = ?", (_session_fingerprint(token),))
            conn.commit()
            conn.close()
            raise HTTPException(status_code=401, detail="Session expired; sign in again")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session timestamp")
    return dict(row)


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/auth/login")
def login(payload: dict):
    username = str(payload.get("username") or "").strip()
    password = payload.get("password")
    if not isinstance(password, str) or not username or not password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user["password_hash"].startswith("pbkdf2_sha256$"):
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(password), user["username"]))

    token = f"wm_{uuid.uuid4().hex}"
    conn.execute(
        "INSERT INTO sessions (token, username, role, created_at) VALUES (?, ?, ?, ?)",
        (_session_fingerprint(token), user["username"], user["role"], datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()
    conn.close()
    return {
        "token": token,
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "service_center_id": user["service_center_id"],
    }


@app.get("/api/mcp/discovery")
def list_mcp_servers_and_tools():
    return {
        "transport": "local_in_process",
        "mcp_protocol_connected": False,
        "description": "Workflow tools use local Python registries. Device research uses a direct Brave Search HTTPS API connector when configured; it is not an MCP transport.",
        "external_connections": {
            "brave_search": "configured" if BRAVE_SEARCH_API_KEY else "not_configured",
            "ollama": "local_http",
        },
        "servers": [
            {
                "server_name": evidence_mcp.server_name,
                "instructions": evidence_mcp.instructions,
                "tools": evidence_mcp.list_tools(),
            },
            {
                "server_name": diagnostic_interview_mcp.server_name,
                "instructions": diagnostic_interview_mcp.instructions,
                "tools": diagnostic_interview_mcp.list_tools(),
            },
            {
                "server_name": policy_rag_mcp.server_name,
                "instructions": policy_rag_mcp.instructions,
                "tools": policy_rag_mcp.list_tools(),
            },
            {
                "server_name": service_ops_mcp.server_name,
                "instructions": service_ops_mcp.instructions,
                "tools": service_ops_mcp.list_tools(),
            },
        ],
    }


@app.get("/api/health/components")
def component_health():
    vision = {"enabled": ENABLE_OLLAMA, "status": "disabled", "model": VISION_MODEL}
    text_model = {"enabled": ENABLE_OLLAMA, "status": "disabled", "model": TEXT_MODEL}
    ollama_models = []
    if ENABLE_OLLAMA:
        try:
            response = httpx.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3.0)
            response.raise_for_status()
            models_data = response.json().get("models", [])
            ollama_models = [m.get("name") for m in models_data]
            installed = set(ollama_models)
            # Match model name with or without :latest suffix
            base_model = VISION_MODEL.split(":")[0]
            matched = any(
                name == VISION_MODEL or name == f"{VISION_MODEL}:latest" or name.startswith(f"{base_model}:")
                for name in installed
            )
            vision["status"] = "ready" if matched else "model_not_installed"
            vision["ollama_reachable"] = True
            vision["installed_models"] = ollama_models
            text_base_model = TEXT_MODEL.split(":")[0]
            text_matched = any(
                name == TEXT_MODEL or name == f"{TEXT_MODEL}:latest" or name.startswith(f"{text_base_model}:")
                for name in installed
            )
            text_model["status"] = "ready" if text_matched else "model_not_installed"
            text_model["ollama_reachable"] = True
            text_model["installed_models"] = ollama_models
        except (httpx.HTTPError, ValueError, Exception) as e:
            vision["status"] = "unreachable"
            vision["ollama_reachable"] = False
            vision["error"] = str(e)[:120]
            text_model["status"] = "unreachable"
            text_model["ollama_reachable"] = False
    return {
        "status": "ok",
        "vision_model": vision,
        "text_model": text_model,
        "ollama_base_url": OLLAMA_BASE_URL,
        "agent": {
            "status": "ready" if text_model.get("status") == "ready" else "degraded",
            "mode": "ollama_reasoning_with_safe_fallback",
            "llm_agent_connected": ENABLE_OLLAMA and text_model.get("status") == "ready",
            "model": TEXT_MODEL,
        },
        "tools": {"status": "ready", "mode": "local_in_process_registry", "mcp_transport_connected": False},
        "external_research": {
            "provider": "Brave Search",
            "status": "configured" if BRAVE_SEARCH_API_KEY else "not_configured",
            "domains": ["support.google.com", "store.google.com", "reddit.com"],
        },
    }


@app.get("/api/config/client")
def client_config():
    return {"demo_mode": ENVIRONMENT not in {"production", "prod"}}


@app.get("/api/orders")
def list_customer_orders(user: dict = Depends(get_current_user)):
    conn = get_conn()
    if user["role"] == "customer":
        rows = conn.execute("SELECT * FROM orders WHERE customer_username = ?", (user["username"],)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/slots")
def get_open_slots(user: dict = Depends(get_current_user)):
    return service_ops_mcp.call_tool("list_available_service_slots", {})


@app.post("/api/cases")
async def create_and_investigate_case(
    order_id: str = Form(...),
    reported_symptom: str = Form(...),
    complaint_description: str = Form(...),
    invoice_text_or_json: Optional[str] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customer accounts can initiate warranty cases")

    conn = get_conn()
    order_row = conn.execute(
        "SELECT * FROM orders WHERE order_id = ? AND customer_username = ?",
        (order_id, user["username"]),
    ).fetchone()
    if not order_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found for this customer")
    order_record = dict(order_row)

    saved_files: List[str] = []
    if photos:
        for upload in photos[:4]:
            if upload.filename:
                if upload.content_type not in ALLOWED_IMAGE_TYPES:
                    conn.close()
                    raise HTTPException(status_code=415, detail="Photo must be a JPEG, PNG, or WebP image")
                raw_bytes = await upload.read(MAX_UPLOAD_BYTES + 1)
                if len(raw_bytes) > MAX_UPLOAD_BYTES:
                    conn.close()
                    raise HTTPException(status_code=413, detail=f"Each photo must be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
                try:
                    from PIL import Image
                    from io import BytesIO
                    with Image.open(BytesIO(raw_bytes)) as image:
                        if image.width * image.height > MAX_IMAGE_PIXELS:
                            raise HTTPException(status_code=413, detail="Photo resolution is too large")
                        image.verify()
                    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[upload.content_type]
                except HTTPException:
                    conn.close()
                    raise
                except Exception:
                    conn.close()
                    raise HTTPException(status_code=415, detail="Uploaded file is not a valid supported image")
                sha = hashlib.sha256(raw_bytes).hexdigest()[:16]
                safe_name = f"{uuid.uuid4().hex}_{sha}{extension}"
                dest = UPLOAD_DIR / safe_name
                dest.write_bytes(raw_bytes)
                saved_files.append(safe_name)

    case_id = f"CASE-{uuid.uuid4().hex[:6].upper()}"
    state = await run_in_threadpool(
        orchestrator.run_initial_investigation,
        case_id=case_id,
        order_record=order_record,
        reported_symptom=reported_symptom,
        complaint_description=complaint_description,
        uploaded_files=saved_files,
        invoice_text_or_json=invoice_text_or_json,
    )

    if saved_files and state["visual_observations"].get("vlm_status") != "available":
        for saved_file in saved_files:
            (UPLOAD_DIR / saved_file).unlink(missing_ok=True)
        conn.close()
        raise HTTPException(
            status_code=503,
            detail=(
                "The uploaded photo could not be checked because the vision model is not available. "
                "No case was created. Start Ollama with the configured vision model, or remove the photo and submit using the written description only."
            ),
        )

    product_relevance = state["visual_observations"].get("product_relevance", "uncertain")
    if saved_files and product_relevance != "consistent":
        for saved_file in saved_files:
            (UPLOAD_DIR / saved_file).unlink(missing_ok=True)
        conn.close()
        feedback = state["visual_observations"].get("vlm_Direct_customer_feedback", "")
        if product_relevance == "inconsistent":
            detail = feedback or f"This photo does not appear to show the selected {order_record['product_model']}. Please upload a clear device photo."
        else:
            detail = f"The image check could not confirm that this photo shows a {order_record['product_category']}. Please upload a clear photo of the device."
        raise HTTPException(
            status_code=422,
            detail=detail,
        )

    now = datetime.utcnow().isoformat() + "Z"
    conn.execute(
        '''INSERT INTO cases
        (case_id, order_id, customer_username, product_category, product_model, serial_number,
         reported_symptom, complaint_description, workflow_status, current_interrupt, state_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            case_id,
            order_id,
            user["username"],
            order_record["product_category"],
            order_record["product_model"],
            order_record["serial_number"],
            reported_symptom,
            complaint_description,
            "AWAITING_DIAGNOSTIC_INTERVIEW",
            state["current_interrupt"],
            json.dumps(state),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return state


@app.post("/api/cases/{case_id}/interview-reply")
def submit_diagnostic_interview_reply(
    case_id: str,
    req: DiagnosticInterviewReplyRequest,
    user: dict = Depends(get_current_user),
):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)
    if user["role"] != "customer" or row["customer_username"] != user["username"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    state = json.loads(row["state_json"])
    if state.get("current_interrupt") != "await_diagnostic_interview":
        conn.close()
        raise HTTPException(status_code=409, detail="Case is not awaiting diagnostic interview answers")
    updated_state = orchestrator.resume_after_diagnostic_interview(
        case_state=state,
        software_update_timing=req.software_update_timing,
        boot_or_screenshot_behavior=req.boot_or_screenshot_behavior,
        additional_customer_notes=req.additional_customer_notes or "",
        answers=req.answers,
    )
    now = datetime.utcnow().isoformat() + "Z"
    conn.execute(
        "UPDATE cases SET workflow_status = ?, current_interrupt = ?, state_json = ?, updated_at = ? WHERE case_id = ?",
        (
            "AWAITING_CUSTOMER_SLOT_CONSENT",
            updated_state["current_interrupt"],
            json.dumps(updated_state),
            now,
            case_id,
        ),
    )
    conn.commit()
    conn.close()
    return updated_state


@app.get("/api/cases")
def list_cases(user: dict = Depends(get_current_user)):
    conn = get_conn()
    if user["role"] == "customer":
        rows = conn.execute(
            "SELECT * FROM cases WHERE customer_username = ? AND product_category IN (?, ?, ?) ORDER BY updated_at DESC",
            (user["username"], *sorted(SUPPORTED_PIXEL_CATEGORIES)),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cases WHERE product_category IN (?, ?, ?) ORDER BY updated_at DESC",
            tuple(sorted(SUPPORTED_PIXEL_CATEGORIES)),
        ).fetchall()
    conn.close()
    return [json.loads(r["state_json"]) for r in rows]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, user: dict = Depends(get_current_user)):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row)
    if user["role"] == "customer" and row["customer_username"] != user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return json.loads(row["state_json"])


@app.post("/api/cases/{case_id}/book-slot")
def approve_and_book_slot(
    case_id: str,
    req: SlotConsentRequest,
    user: dict = Depends(get_current_user),
):
    if not req.customer_consent_accepted:
        raise HTTPException(status_code=400, detail="Explicit customer consent is required to lock a service slot")

    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)
    if user["role"] != "customer" or row["customer_username"] != user["username"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    state = json.loads(row["state_json"])
    if state.get("current_interrupt") != "await_customer_slot_consent":
        conn.close()
        raise HTTPException(status_code=409, detail="Case is not awaiting customer slot consent")
    expected_qv = state["pricing_proposal"]["quote_version"]
    if req.quote_version != expected_qv:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Stale quote version ({req.quote_version} != {expected_qv}). Please review the latest estimate.",
        )

    slot_row = conn.execute("SELECT * FROM service_slots WHERE slot_id = ?", (req.slot_id,)).fetchone()
    if not slot_row or slot_row["is_booked"] == 1:
        conn.close()
        raise HTTPException(status_code=409, detail="Selected service slot is no longer available")

    now = datetime.utcnow().isoformat() + "Z"
    booking_record = {
        "booking_id": f"BK-{uuid.uuid4().hex[:6].upper()}",
        "slot_id": slot_row["slot_id"],
        "center_id": slot_row["center_id"],
        "center_name": slot_row["center_name"],
        "city": slot_row["city"],
        "slot_window": slot_row["slot_window"],
        "approved_quote_version": req.quote_version,
        "customer_consent_timestamp": now,
    }

    conn.execute(
        "UPDATE service_slots SET is_booked = 1, booked_case_id = ? WHERE slot_id = ? AND is_booked = 0",
        (case_id, req.slot_id),
    )
    if conn.execute("SELECT changes()").fetchone()[0] != 1:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="Selected service slot was booked by another customer")
    updated_state = orchestrator.resume_after_slot_booking(state, booking_record)
    conn.execute(
        "UPDATE cases SET workflow_status = ?, current_interrupt = ?, state_json = ?, updated_at = ? WHERE case_id = ?",
        (
            "BOOKED_AWAITING_TECHNICIAN_INSPECTION",
            updated_state["current_interrupt"],
            json.dumps(updated_state),
            now,
            case_id,
        ),
    )
    conn.execute(
        "INSERT INTO outbox_events (event_id, case_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id,
            "APPOINTMENT_BOOKED_JOB_SHEET_V1_READY",
            json.dumps(booking_record),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return updated_state


@app.post("/api/cases/{case_id}/technician-inspection")
def submit_technician_inspection(
    case_id: str,
    report: TechnicianInspectionInput,
    user: dict = Depends(get_current_user),
):
    if user["role"] != "technician":
        raise HTTPException(
            status_code=403,
            detail="Security Guardrail: Only authenticated Service Center Technicians can submit hardware inspection findings.",
        )

    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)

    state = json.loads(row["state_json"])
    if not state.get("booking_record"):
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot submit technician inspection before an appointment is booked")
    if state.get("current_interrupt") != "await_technician_inspection":
        conn.close()
        raise HTTPException(status_code=409, detail="Case is not awaiting technician inspection")
    if user.get("service_center_id") != state["booking_record"].get("center_id"):
        conn.close()
        raise HTTPException(status_code=403, detail="Technician is not assigned to this service center")

    updated_state = orchestrator.resume_after_technician_inspection(
        case_state=state,
        tech_report=report.model_dump(),
        technician_username=user["username"],
    )
    now = datetime.utcnow().isoformat() + "Z"
    new_status = (
        "AWAITING_CUSTOMER_REPAIR_CONSENT"
        if updated_state["final_adjudication"]["requires_customer_paid_repair_consent"]
        else "COMPLETED_UNDER_WARRANTY"
    )

    conn.execute(
        "UPDATE cases SET workflow_status = ?, current_interrupt = ?, state_json = ?, updated_at = ? WHERE case_id = ?",
        (new_status, updated_state["current_interrupt"], json.dumps(updated_state), now, case_id),
    )
    conn.execute(
        "INSERT INTO outbox_events (event_id, case_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            f"EVT-{uuid.uuid4().hex[:8].upper()}",
            case_id,
            "TECHNICIAN_INSPECTION_COMPLETED_JOB_SHEET_V2",
            json.dumps(updated_state["final_adjudication"]),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return updated_state


@app.post("/api/cases/{case_id}/repair-consent")
def submit_customer_repair_consent(
    case_id: str,
    req: RepairOfferConsentRequest,
    user: dict = Depends(get_current_user),
):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only the customer can approve or decline a paid repair offer")

    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row or row["customer_username"] != user["username"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)

    state = json.loads(row["state_json"])
    if state.get("current_interrupt") != "await_customer_repair_consent":
        conn.close()
        raise HTTPException(status_code=409, detail="Case is not awaiting paid repair consent")
    if not state.get("final_adjudication"):
        conn.close()
        raise HTTPException(status_code=400, detail="No post-inspection repair offer is pending")

    now = datetime.utcnow().isoformat() + "Z"
    state["repair_consent"] = {
        "accepted": req.repair_consent_accepted,
        "customer_comment": req.customer_comment or "",
        "timestamp": now,
    }
    state["current_interrupt"] = None
    new_status = "REPAIR_AUTHORIZED_IN_PROGRESS" if req.repair_consent_accepted else "PAID_REPAIR_DECLINED_RETURN_DEVICE"
    state["agent_trace"].append({
        "step": "7. Separate Post-Inspection Paid Repair Consent",
        "mcp_server": "service-ops-mcp-server",
        "tools_called": ["compile_service_job_sheet"],
        "summary": f"Customer {'APPROVED' if req.repair_consent_accepted else 'DECLINED'} final repair quote. Status -> {new_status}.",
    })
    state["job_sheet"] = service_ops_mcp.call_tool(
        "compile_service_job_sheet",
        {"case_state": state, "stage": "final_closed_record"},
    )

    conn.execute(
        "UPDATE cases SET workflow_status = ?, current_interrupt = ?, state_json = ?, updated_at = ? WHERE case_id = ?",
        (new_status, None, json.dumps(state), now, case_id),
    )
    conn.commit()
    conn.close()
    return state


@app.post("/api/cases/{case_id}/escalate")
def escalate_case_to_support(
    case_id: str,
    req: EscalationRequest,
    user: dict = Depends(get_current_user),
):
    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)
    if user["role"] == "customer" and row["customer_username"] != user["username"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized for this case")
    if user["role"] not in ("customer", "support"):
        conn.close()
        raise HTTPException(status_code=403, detail="Only customers or support representatives can escalate a case")

    state = json.loads(row["state_json"])
    updated_state = orchestrator.escalate_to_human_support(state, req.reason, req.customer_message)
    now = datetime.utcnow().isoformat() + "Z"

    conn.execute(
        "UPDATE cases SET workflow_status = ?, current_interrupt = ?, state_json = ?, updated_at = ? WHERE case_id = ?",
        ("ESCALATED_TO_HUMAN_SUPPORT", updated_state["current_interrupt"], json.dumps(updated_state), now, case_id),
    )
    conn.commit()
    conn.close()
    return updated_state


@app.post("/api/cases/{case_id}/support-reply")
def reply_as_human_support(
    case_id: str,
    req: SupportReplyRequest,
    user: dict = Depends(get_current_user),
):
    if user["role"] not in ("support", "customer"):
        raise HTTPException(status_code=403, detail="Only support representatives or the customer can post to the support thread")

    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    _require_pixel_case(row, conn)
    if user["role"] == "customer" and row["customer_username"] != user["username"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    state = json.loads(row["state_json"])
    now = datetime.utcnow().isoformat() + "Z"
    state["support_thread"].append({
        "sender_role": user["role"],
        "sender_name": user["full_name"],
        "message": req.message,
        "resolution_action": req.resolution_action,
        "timestamp": now,
    })

    if user["role"] == "customer" and req.resolution_action is not None:
        conn.close()
        raise HTTPException(status_code=403, detail="Only support representatives can apply resolution actions")

    if user["role"] == "support" and req.resolution_action == "waive_diagnostic_fee":
        for s in state["pricing_proposal"]["preliminary_scenarios"]:
            s["diagnostic_fee_inr"] = 0
            s["notes"] += " [Diagnostic fee waived by Senior Support Specialist]"
        state["agent_trace"].append({
            "step": "Human Support Override Applied",
            "mcp_server": "service-ops-mcp-server",
            "tools_called": ["compile_service_job_sheet"],
            "summary": f"Support specialist {user['username']} waived upfront diagnostic fee and updated case record.",
        })

    state["job_sheet"] = service_ops_mcp.call_tool(
        "compile_service_job_sheet",
        {"case_state": state, "stage": "support_updated"},
    )

    conn.execute(
        "UPDATE cases SET state_json = ?, updated_at = ? WHERE case_id = ?",
        (json.dumps(state), now, case_id),
    )
    conn.commit()
    conn.close()
    return state
