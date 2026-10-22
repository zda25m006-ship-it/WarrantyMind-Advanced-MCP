import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warrantymind.database import seed_demo_data, get_conn
from warrantymind.mcp_servers.evidence_mcp import evidence_mcp
from warrantymind.mcp_servers.diagnostic_interview_mcp import diagnostic_interview_mcp
from warrantymind.mcp_servers.policy_rag_mcp import policy_rag_mcp
from warrantymind.mcp_servers.service_ops_mcp import service_ops_mcp
from warrantymind.orchestrator.graph import orchestrator


def test_mcp_servers_discovery_and_contracts():
    assert len(evidence_mcp.list_tools()) == 2
    assert len(diagnostic_interview_mcp.list_tools()) == 2
    assert len(policy_rag_mcp.list_tools()) == 1
    assert len(service_ops_mcp.list_tools()) == 3


def test_vlm_suspicion_and_interactive_diagnostic_interview_to_resolution():
    seed_demo_data()
    conn = get_conn()
    order = dict(conn.execute("SELECT * FROM orders WHERE order_id = 'ORD-1001'").fetchone())
    slot = dict(conn.execute("SELECT * FROM service_slots WHERE slot_id = 'SLOT-MAA-01'").fetchone())
    conn.close()

    # 1. Customer uploads green-line photo -> VLM inspects & suspects post-update / OLED driver issue -> pauses for Diagnostic Interview
    state = orchestrator.run_initial_investigation(
        case_id="CASE-VLM01",
        order_record=order,
        reported_symptom="Green vertical OLED line on display",
        complaint_description="My phone suddenly developed a bright vertical green line down the right side of the OLED screen. Never dropped.",
        uploaded_files=["ORD-1001_b894d28dde45_green-lines-iphone-screen.jpg"],
    )
    assert state["visual_observations"]["vlm_suspected_origin"] == "needs_more_visual_or_symptom_context"
    assert state["visual_observations"]["vlm_status"] in {"not_attempted", "unavailable"}
    assert "could not be visually verified" in state["visual_observations"]["vlm_Direct_customer_feedback"]
    assert state["current_interrupt"] == "await_diagnostic_interview"
    assert len(state["diagnostic_interview"]["questions"]) == 2

    # 2. Customer answers the Agent's real-time software update & screenshot/boot-logo questions
    state = orchestrator.resume_after_diagnostic_interview(
        case_state=state,
        software_update_timing="Yes — I updated the software a few days ago and the line appeared right after",
        boot_or_screenshot_behavior="NOT visible in a screenshot, but stays visible on the black Apple boot screen (Confirms OLED Hardware Driver)",
        additional_customer_notes="Phone was on the desk charging during the update.",
    )
    assert state["diagnostic_interview"]["status"] == "completed"
    assert state["diagnostic_interview"]["software_vs_hardware_conclusion"] == "likely_hardware_component_fault_triggered_post_update_or_spontaneous"
    assert state["current_interrupt"] == "await_customer_slot_consent"

    # 3. Customer books slot -> Technician inspects -> Free Warranty Repair Approved
    state = orchestrator.resume_after_slot_booking(
        state,
        {
            "booking_id": "BK-VLM01",
            "slot_id": slot["slot_id"],
            "center_id": slot["center_id"],
            "center_name": slot["center_name"],
            "city": slot["city"],
            "slot_window": slot["slot_window"],
            "approved_quote_version": state["pricing_proposal"]["quote_version"],
        },
    )
    state = orchestrator.resume_after_technician_inspection(
        case_state=state,
        tech_report={
            "serial_verified": True,
            "physical_impact_damage": False,
            "liquid_contact_detected": False,
            "confirmed_fault_component": "display_module",
            "technician_notes": "Confirmed post-update OLED column driver fault, LCI intact.",
        },
        technician_username="technician1",
    )
    assert state["final_adjudication"]["final_outcome"] == "APPROVED_FREE_WARRANTY_OR_PROGRAM_REPAIR"
    assert state["final_adjudication"]["final_repair_cost_inr"] == 0


if __name__ == "__main__":
    test_mcp_servers_discovery_and_contracts()
    print("[PASS] test_mcp_servers_discovery_and_contracts (4 MCP Servers)")
    test_vlm_suspicion_and_interactive_diagnostic_interview_to_resolution()
    print("[PASS] test_vlm_suspicion_and_interactive_diagnostic_interview_to_resolution")
    print("All v3.1 interactive VLM & diagnostic agent tests passed!")
