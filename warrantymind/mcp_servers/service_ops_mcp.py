import hashlib
from typing import Dict, Any, List
from warrantymind.database import get_conn
from warrantymind.schemas import PriceEstimateScenario
from warrantymind.mcp_servers.protocol import LocalFastMCPRegistry

service_ops_mcp = LocalFastMCPRegistry(
    server_name="service-ops-mcp-server",
    instructions="Local repair-price lookup (empty until approved Pixel pricing is configured), demo service-review slots, consent checks, and two-stage Job Sheet generation.",
)


@service_ops_mcp.tool(
    name="get_preliminary_repair_estimates",
    description="Looks up component estimates from the local price catalogue. Pixel estimates remain unavailable until an approved source is configured.",
    input_schema={
        "type": "object",
        "properties": {
            "product_category": {"type": "string"},
            "observable_symptoms": {"type": "array", "items": {"type": "string"}},
            "preliminary_eligibility": {"type": "string"},
        },
        "required": ["product_category", "observable_symptoms", "preliminary_eligibility"],
    },
)
def get_preliminary_repair_estimates(
    product_category: str,
    observable_symptoms: List[str],
    preliminary_eligibility: str,
) -> Dict[str, Any]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM price_catalog WHERE product_category = ?",
        (product_category,),
    ).fetchall()
    conn.close()

    if not rows:
        quote_seed = f"{product_category}:{preliminary_eligibility}:unpriced"
        quote_version = "PENDING-" + hashlib.sha256(quote_seed.encode("utf-8")).hexdigest()[:8].upper()
        return {
            "quote_version": quote_version,
            "quote_status": "not_configured",
            "covered_if_inspection_passes": None,
            "preliminary_scenarios": [],
            "message": "No approved Pixel repair-price catalogue is configured. No repair price, fee, or coverage amount has been invented.",
        }

    covered_candidate = preliminary_eligibility in (
        "ELIGIBLE_PENDING_PHYSICAL_INSPECTION",
        "SPECIAL_PROGRAM_CANDIDATE_PENDING_INSPECTION",
    )

    scenarios: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        note = (
            "₹0 if technician inspection confirms covered defect & zero liquid/impact exclusions; "
            f"otherwise ₹{d['repair_min_inr']:,}–₹{d['repair_max_inr']:,} (requires separate repair consent)."
            if covered_candidate
            else f"Out-of-warranty / excluded preliminary estimate: ₹{d['repair_min_inr']:,}–₹{d['repair_max_inr']:,} + ₹{d['diagnostic_fee_inr']:,} diagnostic fee."
        )
        scenarios.append(
            PriceEstimateScenario(
                component_code=d["component_code"],
                component_name=d["component_name"],
                diagnostic_fee_inr=0 if covered_candidate else d["diagnostic_fee_inr"],
                repair_min_inr=d["repair_min_inr"],
                repair_max_inr=d["repair_max_inr"],
                covered_if_inspection_passes=covered_candidate,
                catalog_version=d["catalog_version"],
                notes=note,
            ).model_dump()
        )

    quote_seed = f"{product_category}:{preliminary_eligibility}:{len(scenarios)}"
    quote_version = "QV-" + hashlib.sha256(quote_seed.encode("utf-8")).hexdigest()[:8].upper()

    return {
        "quote_version": quote_version,
        "quote_status": "catalogue_estimate",
        "covered_if_inspection_passes": covered_candidate,
        "preliminary_scenarios": scenarios,
        "message": "Catalogue estimates are preliminary and require a human to verify the applicable warranty terms.",
    }


@service_ops_mcp.tool(
    name="list_available_service_slots",
    description="Returns unbooked WarrantyMind demo service-review slots; these are not Google-authorized appointments.",
    input_schema={"type": "object", "properties": {}},
)
def list_available_service_slots() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM service_slots WHERE is_booked = 0 ORDER BY slot_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@service_ops_mcp.tool(
    name="compile_service_job_sheet",
    description="Assembles the structured 7-section Job Sheet (v1 Pre-Inspection or v2 Final Post-Inspection) from verified case state.",
    input_schema={
        "type": "object",
        "properties": {
            "case_state": {"type": "object"},
            "stage": {"type": "string"},
        },
        "required": ["case_state", "stage"],
    },
)
def compile_service_job_sheet(case_state: Dict[str, Any], stage: str = "v1_pre_inspection") -> Dict[str, Any]:
    order = case_state.get("order_record", {})
    vis = case_state.get("visual_observations", {})
    diag = case_state.get("diagnostic_interview", {})
    inv = case_state.get("invoice_extraction", {})
    pol = case_state.get("policy_assessment", {})
    pricing = case_state.get("pricing_proposal", {})
    booking = case_state.get("booking_record")
    tech_report = case_state.get("technician_report")
    final_decision = case_state.get("final_adjudication")
    support_history = case_state.get("support_thread", [])

    return {
        "job_sheet_version": "v2_final_adjudication" if tech_report else "v1_pre_inspection",
        "generated_stage": stage,
        "section_1_customer_and_product": {
            "case_id": case_state.get("case_id"),
            "customer_username": order.get("customer_username"),
            "product_category": order.get("product_category"),
            "product_model": order.get("product_model"),
            "serial_number": order.get("serial_number"),
            "serial_verified_by_technician": bool(tech_report and tech_report.get("serial_verified")),
        },
        "section_2_customer_complaint": {
            "reported_symptom": case_state.get("reported_symptom"),
            "complaint_description": case_state.get("complaint_description"),
        },
        "section_3_evidence_inventory": {
            "uploaded_photos": case_state.get("uploaded_files", []),
            "pixel_inspection_telemetry": vis.get("pixel_inspection_telemetry", {}),
            "invoice_verification": inv,
        },
        "section_4_vlm_observations_and_diagnostic_interview": {
            "observable_symptoms": vis.get("observable_symptoms", []),
            "visible_external_damage": vis.get("visible_external_damage"),
            "vlm_direct_customer_feedback": vis.get("vlm_Direct_customer_feedback"),
            "vlm_suspected_origin": vis.get("vlm_suspected_origin"),
            "diagnostic_interview_status": diag.get("status"),
            "customer_interview_answers": diag.get("customer_answers", []),
            "refined_diagnosis_hypothesis": diag.get("refined_diagnosis_hypothesis"),
            "software_vs_hardware_conclusion": diag.get("software_vs_hardware_conclusion"),
            "diagnostic_agent_status": diag.get("agent_status"),
            "diagnostic_agent_model": diag.get("agent_model"),
            "diagnostic_confidence": diag.get("confidence"),
            "customer_facing_agent_response": diag.get("customer_response"),
            "diagnostic_source_citations": diag.get("source_citations", []),
            "diagnostic_evidence_gaps": diag.get("evidence_gaps", []),
            "remote_root_cause_status": vis.get("internal_or_liquid_cause"),
        },
        "section_5_warranty_and_hybrid_rag_assessment": {
            "standard_warranty_active": pol.get("standard_warranty_active"),
            "warranty_expiry": pol.get("standard_warranty_expiry"),
            "eligible_special_programs": pol.get("eligible_special_programs", []),
            "preliminary_eligibility": pol.get("preliminary_eligibility"),
            "cited_clauses": pol.get("citations", []),
            "policy_explanation": pol.get("policy_explanation"),
            "official_google_sources": case_state.get("device_research", {}).get("warranty_research", {}).get("sources", []),
            "community_sources_anecdotal": case_state.get("device_research", {}).get("community_research", {}).get("sources", []),
            "human_review_required": pol.get("decision_authority") == "human_support_review_required",
        },
        "section_6_service_booking_and_technician_findings": {
            "quote_version": pricing.get("quote_version"),
            "preliminary_price_scenarios": pricing.get("preliminary_scenarios", []),
            "appointment_booking": booking,
            "technician_checklist": [
                "Verify device serial number against Order DB",
                "Inspect external enclosure and display glass under magnification",
                "Check internal Liquid Contact Indicators (LCI)",
                "Run display / power controller hardware diagnostics (correlate with customer post-update interview notes)",
            ],
            "technician_inspection_report": tech_report,
            "final_adjudication_and_offer": final_decision,
            "customer_repair_consent": case_state.get("repair_consent"),
        },
        "section_7_support_and_escalation_history": {
            "escalated_to_human": bool(case_state.get("support_handoff")),
            "structured_support_handoff": case_state.get("support_handoff"),
            "conversation_messages": support_history,
        },
    }
