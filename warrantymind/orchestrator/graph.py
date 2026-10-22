from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from warrantymind.agents.research import collect_device_research
from warrantymind.mcp_servers.evidence_mcp import evidence_mcp
from warrantymind.mcp_servers.diagnostic_interview_mcp import diagnostic_interview_mcp
from warrantymind.mcp_servers.policy_rag_mcp import policy_rag_mcp
from warrantymind.mcp_servers.service_ops_mcp import service_ops_mcp


class WarrantyMindOrchestrator:
    '''
    Local workflow supervisor coordinating evidence, Ollama reasoning, source research,
    internal guidance retrieval, and demo service operations through Python registries.
    '''

    def run_initial_investigation(
        self,
        case_id: str,
        order_record: Dict[str, Any],
        reported_symptom: str,
        complaint_description: str,
        uploaded_files: List[str],
        invoice_text_or_json: Optional[str] = None,
    ) -> Dict[str, Any]:
        trace_log: List[Dict[str, Any]] = []

        vis_obs = evidence_mcp.call_tool(
            "inspect_device_photos",
            {
                "product_category": order_record["product_category"],
                "product_model": order_record["product_model"],
                "reported_symptom": reported_symptom,
                "complaint_description": complaint_description,
                "uploaded_files": uploaded_files,
            },
        )
        # Reject unrelated or unverified uploads before invoice parsing, web search, or LLM synthesis.
        if uploaded_files and (
            vis_obs.get("vlm_status") != "available"
            or vis_obs.get("product_relevance") != "consistent"
        ):
            return {
                "visual_observations": vis_obs,
                "current_interrupt": None,
            }
        inv_obs = evidence_mcp.call_tool(
            "extract_invoice_metadata",
            {"order_record": order_record, "invoice_text_or_json": invoice_text_or_json},
        )
        trace_log.append({
            "step": "1. Pixel photo and invoice inspection",
            "agent": "Ollama Vision and Evidence Agent" if vis_obs.get("vlm_status") == "available" else "Evidence Agent",
            "source": "local Ollama VLM + image checks",
            "summary": (
                f"Inspected {len(uploaded_files)} photo(s). Image match: {vis_obs.get('product_relevance')}; "
                f"visible observations: {', '.join(vis_obs.get('observable_symptoms', [])) or 'none reported'}."
            ),
        })

        device_research = collect_device_research(order_record, vis_obs, reported_symptom)
        warranty_research = device_research["warranty_research"]
        community_research = device_research["community_research"]
        trace_log.append({
            "step": "2. Official warranty research",
            "agent": warranty_research["agent"],
            "source": warranty_research.get("provider") or "not configured",
            "summary": f"{warranty_research['status']}: {len(warranty_research.get('sources', []))} Google-domain source(s). {warranty_research.get('message', '')}",
        })
        trace_log.append({
            "step": "3. Community research",
            "agent": community_research["agent"],
            "source": community_research.get("provider") or "not configured",
            "summary": f"{community_research['status']}: {len(community_research.get('sources', []))} community source(s). Reports are anecdotal, not policy evidence.",
        })

        rag_query = f"{order_record['product_model']} {reported_symptom} {' '.join(vis_obs.get('observable_symptoms', []))}"
        policy_res = policy_rag_mcp.call_tool(
            "retrieve_pixel_warranty_guidance",
            {
                "order_record": order_record,
                "visual_observations": vis_obs,
                "query": rag_query,
                "device_research": device_research,
            },
        )
        diag_interview = diagnostic_interview_mcp.call_tool(
            "create_research_grounded_diagnostic_interview",
            {
                "order_record": order_record,
                "product_model": order_record["product_model"],
                "visual_observations": vis_obs,
                "reported_symptom": reported_symptom,
                "complaint_description": complaint_description,
                "device_research": device_research,
                "policy_assessment": policy_res,
            },
        )
        trace_log.append({
            "step": "4. Ollama diagnostic synthesis",
            "agent": "Ollama Pixel Diagnostic Agent",
            "source": diag_interview.get("agent_model", "local fallback"),
            "summary": (
                f"Agent status: {diag_interview.get('agent_status')}; confidence: {diag_interview.get('confidence')}; "
                f"generated {len(diag_interview.get('questions', []))} follow-up question(s). "
                f"Coverage is {policy_res['preliminary_eligibility']}."
            ),
        })

        pricing_res = service_ops_mcp.call_tool(
            "get_preliminary_repair_estimates",
            {
                "product_category": order_record["product_category"],
                "observable_symptoms": vis_obs.get("observable_symptoms", []),
                "preliminary_eligibility": policy_res["preliminary_eligibility"],
            },
        )
        available_slots = service_ops_mcp.call_tool("list_available_service_slots", {})
        trace_log.append({
            "step": "5. Service workflow readiness",
            "agent": "Service Operations",
            "source": "local demo registry",
            "summary": pricing_res.get("message", "No binding price was calculated."),
        })

        case_state = {
            "case_id": case_id,
            "order_record": order_record,
            "reported_symptom": reported_symptom,
            "complaint_description": complaint_description,
            "uploaded_files": uploaded_files,
            "visual_observations": vis_obs,
            "device_research": device_research,
            "diagnostic_interview": diag_interview,
            "invoice_extraction": inv_obs,
            "policy_assessment": policy_res,
            "pricing_proposal": pricing_res,
            "available_slots_snapshot": available_slots,
            "booking_record": None,
            "technician_report": None,
            "final_adjudication": None,
            "repair_consent": None,
            "support_handoff": None,
            "support_thread": [],
            "agent_trace": trace_log,
            "current_interrupt": "await_diagnostic_interview",
        }
        case_state["job_sheet"] = service_ops_mcp.call_tool(
            "compile_service_job_sheet",
            {"case_state": case_state, "stage": "pixel_research_awaiting_customer_answers"},
        )
        return case_state
    def resume_after_diagnostic_interview(
        self,
        case_state: Dict[str, Any],
        software_update_timing: str = "",
        boot_or_screenshot_behavior: str = "",
        additional_customer_notes: str = "",
        answers: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        interview = case_state.get("diagnostic_interview", {})
        normalized_answers = [item for item in (answers or []) if isinstance(item, dict) and str(item.get("answer", "")).strip()]
        if not normalized_answers:
            for index, answer in enumerate([software_update_timing, boot_or_screenshot_behavior]):
                if answer:
                    question = (interview.get("questions") or [{}] * 2)[index]
                    normalized_answers.append({
                        "question_id": question.get("question_id", f"q_{index + 1}"),
                        "question": question.get("question_text", "Customer follow-up"),
                        "answer": answer,
                    })
        if additional_customer_notes:
            normalized_answers.append({
                "question_id": "customer_notes",
                "question": "Additional customer context",
                "answer": additional_customer_notes,
            })

        updated_diag = diagnostic_interview_mcp.call_tool(
            "reanalyze_customer_answers_with_ollama",
            {
                "order_record": case_state["order_record"],
                "reported_symptom": case_state["reported_symptom"],
                "complaint_description": case_state["complaint_description"],
                "visual_observations": case_state["visual_observations"],
                "device_research": case_state.get("device_research", {}),
                "policy_assessment": case_state["policy_assessment"],
                "interview_state": interview,
                "answers": normalized_answers,
            },
        )
        case_state["diagnostic_interview"] = updated_diag
        case_state["current_interrupt"] = "await_customer_slot_consent"
        case_state["agent_trace"].append({
            "step": "6. Ollama reassessment after customer answers",
            "agent": "Ollama Pixel Diagnostic Agent",
            "source": updated_diag.get("agent_model", "local fallback"),
            "summary": (
                f"Status: {updated_diag.get('agent_status')}; confidence: {updated_diag.get('confidence')}; "
                f"assessment: {updated_diag.get('refined_diagnosis_hypothesis')}"
            ),
        })
        case_state["job_sheet"] = service_ops_mcp.call_tool(
            "compile_service_job_sheet",
            {"case_state": case_state, "stage": "research_grounded_customer_answers"},
        )
        return case_state
    def resume_after_slot_booking(
        self,
        case_state: Dict[str, Any],
        booking_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        case_state["booking_record"] = booking_record
        case_state["current_interrupt"] = "await_technician_inspection"
        case_state["agent_trace"].append({
            "step": "5. Customer Slot Consent & Pre-Inspection Checkpoint",
            "mcp_server": "service-ops-mcp-server",
            "tools_called": ["compile_service_job_sheet"],
            "summary": f"Locked slot {booking_record['slot_id']} at {booking_record['center_name']}. Generated Pre-Inspection Job Sheet v1. Workflow paused at interrupt('await_technician_inspection').",
        })
        case_state["job_sheet"] = service_ops_mcp.call_tool(
            "compile_service_job_sheet",
            {"case_state": case_state, "stage": "v1_pre_inspection"},
        )
        return case_state

    def resume_after_technician_inspection(
        self,
        case_state: Dict[str, Any],
        tech_report: Dict[str, Any],
        technician_username: str,
    ) -> Dict[str, Any]:
        case_state["technician_report"] = {
            **tech_report,
            "inspected_by": technician_username,
            "inspected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        pol = case_state["policy_assessment"]
        scenarios = case_state["pricing_proposal"]["preliminary_scenarios"]
        comp_code = tech_report["confirmed_fault_component"]
        matched_scenario = next(
            (s for s in scenarios if s["component_code"] == comp_code),
            scenarios[0] if scenarios else {
                "component_code": comp_code,
                "component_name": "Repair quote not configured",
                "repair_min_inr": 0,
                "repair_max_inr": 0,
            },
        )

        has_exclusion = bool(tech_report["physical_impact_damage"] or tech_report["liquid_contact_detected"])
        was_eligible_candidate = pol["preliminary_eligibility"] in (
            "ELIGIBLE_PENDING_PHYSICAL_INSPECTION",
            "SPECIAL_PROGRAM_CANDIDATE_PENDING_INSPECTION",
        )
        manual_policy_review = pol.get("preliminary_eligibility") == "REQUIRES_OFFICIAL_POLICY_VERIFICATION"

        if not tech_report["serial_verified"]:
            final_outcome = "REJECTED_SERIAL_MISMATCH"
            final_cost_inr = 0
            requires_paid_consent = False
            explanation = "The technician found a serial mismatch. A human must reconcile the order and device identity before making any warranty decision."
        elif comp_code == "no_fault_found":
            final_outcome = "NO_HARDWARE_FAULT_FOUND"
            final_cost_inr = 0
            requires_paid_consent = False
            explanation = "The technician did not confirm a hardware fault. Warranty coverage and any service charge still require verification against applicable official terms."
        elif manual_policy_review:
            final_outcome = "AWAITING_HUMAN_POLICY_REVIEW"
            final_cost_inr = 0
            requires_paid_consent = False
            explanation = "The inspection is recorded, but the app has no verified Google warranty decision or approved Pixel repair quote. A support specialist must review official terms and confirm any costs before asking the customer to approve paid work."
        elif was_eligible_candidate and not has_exclusion:
            final_outcome = "APPROVED_FREE_WARRANTY_OR_PROGRAM_REPAIR"
            final_cost_inr = 0
            requires_paid_consent = False
            explanation = "An authorized human reviewer verified coverage, and the technician confirmed the defect without a recorded exclusion."
        elif not scenarios:
            final_outcome = "AWAITING_HUMAN_POLICY_REVIEW"
            final_cost_inr = 0
            requires_paid_consent = False
            explanation = "No approved repair-price catalogue entry exists for this Pixel device. A human must verify coverage and obtain an official quote before requesting repair consent."
        else:
            final_outcome = "PAID_REPAIR_QUOTE_ISSUED_AWAITING_CONSENT"
            final_cost_inr = matched_scenario["repair_min_inr"]
            requires_paid_consent = True
            explanation = (
                f"A human-verified policy assessment found that complimentary coverage does not apply. "
                f"The approved catalogue quote for {matched_scenario['component_name']} starts at {final_cost_inr:,}. "
                "Work will begin only after the customer explicitly approves the final quote."
            )

        case_state["final_adjudication"] = {
            "final_outcome": final_outcome,
            "confirmed_component": matched_scenario.get("component_name", comp_code),
            "final_repair_cost_inr": final_cost_inr,
            "requires_customer_paid_repair_consent": requires_paid_consent,
            "human_review_required": final_outcome == "AWAITING_HUMAN_POLICY_REVIEW",
            "adjudication_explanation": explanation,
            "governing_citations": pol.get("citations", []),
        }

        case_state["current_interrupt"] = (
            "await_human_policy_review"
            if final_outcome == "AWAITING_HUMAN_POLICY_REVIEW"
            else "await_customer_repair_consent" if requires_paid_consent else "completed_covered_repair"
        )
        case_state["agent_trace"].append({
            "step": "6. Post-Inspection Policy & Quote Re-Adjudication",
            "mcp_server": "service-ops-mcp-server",
            "tools_called": ["compile_service_job_sheet"],
            "summary": f"Resumed from technician report by {technician_username}. Final outcome: {final_outcome} (₹{final_cost_inr:,}). Generated Job Sheet v2.",
        })

        case_state["job_sheet"] = service_ops_mcp.call_tool(
            "compile_service_job_sheet",
            {"case_state": case_state, "stage": "v2_final_adjudication"},
        )
        return case_state

    def escalate_to_human_support(
        self,
        case_state: Dict[str, Any],
        reason: str,
        customer_message: str,
    ) -> Dict[str, Any]:
        pol = case_state["policy_assessment"]
        vis = case_state["visual_observations"]
        research = case_state.get("device_research", {})
        diag = case_state.get("diagnostic_interview", {})
        handoff = {
            "escalated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "dispute_reason": reason,
            "customer_complaint_summary": f"{case_state['order_record']['product_model']} — {case_state['reported_symptom']}: {case_state['complaint_description']}",
            "evidence_reviewed": {
                "photos_count": len(case_state.get("uploaded_files", [])),
                "observable_symptoms": vis.get("observable_symptoms", []),
                "vlm_suspected_origin": vis.get("vlm_suspected_origin"),
                "invoice_status": case_state["invoice_extraction"].get("verification_status"),
            },
            "ai_policy_recommendation": pol.get("preliminary_eligibility"),
            "cited_policy_clauses": pol.get("citations", []),
            "research_brief": {
                "customer_facing_ai_response": diag.get("customer_response") or diag.get("agent_opening_message"),
                "diagnostic_hypothesis": diag.get("refined_diagnosis_hypothesis"),
                "confidence": diag.get("confidence", "low"),
                "evidence_gaps": diag.get("evidence_gaps", []),
                "official_warranty_research": research.get("warranty_research", {}),
                "community_research": research.get("community_research", {}),
                "retrieved_internal_guidance": pol.get("retrieved_clauses", []),
                "human_decision_required": True,
            },
            "unresolved_customer_objection": customer_message,
            "recommended_support_actions": [
                "Check official Google policy links for the device market, model, purchase date, and purchase channel",
                "Review the Pixel community reports as anecdotal troubleshooting context only",
                "Confirm any coverage, service partner, and price with an authorized human source before replying",
            ],
        }
        case_state["support_handoff"] = handoff
        case_state["support_thread"].append({
            "sender_role": "customer",
            "sender_name": case_state["order_record"]["customer_username"],
            "message": customer_message,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        case_state["current_interrupt"] = "await_human_support_resolution"
        case_state["agent_trace"].append({
            "step": "Support Escalation Subgraph — Human Handoff Created",
            "mcp_server": "service-ops-mcp-server",
            "tools_called": ["compile_service_job_sheet"],
            "summary": f"Customer disputed recommendation ({reason}). Generated structured Support Handoff Packet with citations {', '.join(pol.get('citations', []))}.",
        })
        case_state["job_sheet"] = service_ops_mcp.call_tool(
            "compile_service_job_sheet",
            {"case_state": case_state, "stage": "escalated_to_support"},
        )
        return case_state


orchestrator = WarrantyMindOrchestrator()
