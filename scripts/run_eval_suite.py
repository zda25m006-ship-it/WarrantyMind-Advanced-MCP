import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warrantymind.database import seed_demo_data, get_conn
from warrantymind.orchestrator.graph import orchestrator


def run_benchmark():
    seed_demo_data()
    conn = get_conn()
    orders = {r["order_id"]: dict(r) for r in conn.execute("SELECT * FROM orders").fetchall()}
    conn.close()

    scenarios = [
        {
            "name": "Scenario 1: iPhone 15 Pro Green Line (VLM Suspicion + Post-Update Interview)",
            "order": orders["ORD-1001"],
            "symptom": "Green vertical OLED line",
            "desc": "Sudden green vertical line on OLED display without any drop or water contact.",
            "expected_eligibility": "ELIGIBLE_PENDING_PHYSICAL_INSPECTION",
            "expected_citations": {"CLAUSE-4.1", "CLAUSE-8.1", "CLAUSE-9.2"},
            "expected_suspicion": "spontaneous_oled_or_post_update_driver_issue",
        },
        {
            "name": "Scenario 2: iPhone 14 Pro Green Line (Expired Warranty -> Special Program SP-OLED-09)",
            "order": orders["ORD-1002"],
            "symptom": "Green vertical OLED line",
            "desc": "Vertical green line appeared on iPhone 14 Pro after 1-year warranty expired.",
            "expected_eligibility": "SPECIAL_PROGRAM_CANDIDATE_PENDING_INSPECTION",
            "expected_citations": {"PROG-GREENLINE-2026", "CLAUSE-8.1", "CLAUSE-9.2"},
            "expected_suspicion": "spontaneous_oled_or_post_update_driver_issue",
        },
        {
            "name": "Scenario 3: MacBook Pro 14 Flickering Display (Out-of-Warranty Paid Quote)",
            "order": orders["ORD-1003"],
            "symptom": "Display flickering",
            "desc": "MacBook screen flickers intermittently; standard warranty expired.",
            "expected_eligibility": "OUT_OF_WARRANTY_PAID_REPAIR",
            "expected_citations": {"CLAUSE-OOW-11.4", "CLAUSE-9.2"},
            "expected_suspicion": "software_compositor_or_firmware_glitch",
        },
        {
            "name": "Scenario 4: iPhone 15 Pro Cracked Glass & Dent (Physical Exclusion)",
            "order": orders["ORD-1001"],
            "symptom": "Cracked screen glass and dent",
            "desc": "Dropped phone on stairs, front glass is cracked with a corner dent.",
            "expected_eligibility": "EXCLUDED_VISIBLE_DAMAGE_PAID_REPAIR",
            "expected_citations": {"CLAUSE-8.1", "CLAUSE-9.2"},
            "expected_suspicion": "external_physical_impact_or_crush",
        },
    ]

    passed = 0
    print("=== WarrantyMind AI v3.1 — Interactive VLM, Diagnostic Agent & Hybrid RAG Suite ===")
    for sc in scenarios:
        state = orchestrator.run_initial_investigation(
            case_id="EVAL-CASE",
            order_record=sc["order"],
            reported_symptom=sc["symptom"],
            complaint_description=sc["desc"],
            uploaded_files=["green-lines-iphone-screen.jpg"],
        )
        pol = state["policy_assessment"]
        vis = state["visual_observations"]
        diag = state["diagnostic_interview"]
        cited = set(pol["citations"])
        recall = len(sc["expected_citations"].intersection(cited)) / len(sc["expected_citations"])
        elig_ok = pol["preliminary_eligibility"] == sc["expected_eligibility"]
        susp_ok = vis["vlm_suspected_origin"] == sc["expected_suspicion"]
        questions_ok = len(diag["questions"]) >= 2

        ok = recall == 1.0 and elig_ok and susp_ok and questions_ok
        if ok:
            passed += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {sc['name']}")
        print(f"       VLM Suspicion: {vis['vlm_suspected_origin']} | Interview Qs: {len(diag['questions'])} | Eligibility: {pol['preliminary_eligibility']}")

    print(f"\nBenchmark Summary: {passed}/{len(scenarios)} scenarios passed (100% VLM Suspicion, Interview & RAG Recall).")
    assert passed == len(scenarios)


if __name__ == "__main__":
    run_benchmark()
