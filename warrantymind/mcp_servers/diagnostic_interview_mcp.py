from typing import Any, Dict, List, Optional

from warrantymind.agents.ollama_case_agent import OllamaCaseAgent
from warrantymind.mcp_servers.protocol import LocalFastMCPRegistry

diagnostic_interview_mcp = LocalFastMCPRegistry(
    server_name="pixel-diagnostic-agent",
    instructions="Ollama-powered Pixel diagnostic interviewer grounded in image observations, official warranty retrieval, community reports, and customer answers.",
)
_case_agent = OllamaCaseAgent()


@diagnostic_interview_mcp.tool(
    name="create_research_grounded_diagnostic_interview",
    description="Uses the configured Ollama text model to synthesize VLM observations, Google warranty research, community reports, and internal workflow guidance into a customer response and focused questions.",
    input_schema={
        "type": "object",
        "properties": {
            "order_record": {"type": "object"},
            "product_model": {"type": "string"},
            "visual_observations": {"type": "object"},
            "reported_symptom": {"type": "string"},
            "complaint_description": {"type": "string"},
            "device_research": {"type": "object"},
            "policy_assessment": {"type": "object"},
        },
        "required": ["order_record", "visual_observations", "reported_symptom", "complaint_description", "device_research", "policy_assessment"],
    },
)
def generate_diagnostic_questions(
    order_record: Dict[str, Any],
    visual_observations: Dict[str, Any],
    reported_symptom: str,
    complaint_description: str,
    device_research: Dict[str, Any],
    policy_assessment: Dict[str, Any],
    product_model: Optional[str] = None,
) -> Dict[str, Any]:
    return _case_agent.create_initial_response(
        order_record=order_record,
        reported_symptom=reported_symptom,
        complaint_description=complaint_description,
        visual_observations=visual_observations,
        device_research=device_research,
        policy_assessment=policy_assessment,
    )


@diagnostic_interview_mcp.tool(
    name="reanalyze_customer_answers_with_ollama",
    description="Reassesses a Pixel case with Ollama using customer answers, image observations, retrieved source excerpts, and policy guardrails.",
    input_schema={
        "type": "object",
        "properties": {
            "order_record": {"type": "object"},
            "reported_symptom": {"type": "string"},
            "complaint_description": {"type": "string"},
            "visual_observations": {"type": "object"},
            "device_research": {"type": "object"},
            "policy_assessment": {"type": "object"},
            "interview_state": {"type": "object"},
            "answers": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["order_record", "reported_symptom", "complaint_description", "visual_observations", "device_research", "policy_assessment", "interview_state", "answers"],
    },
)
def evaluate_customer_interview_answers(
    order_record: Dict[str, Any],
    reported_symptom: str,
    complaint_description: str,
    visual_observations: Dict[str, Any],
    device_research: Dict[str, Any],
    policy_assessment: Dict[str, Any],
    interview_state: Dict[str, Any],
    answers: List[Dict[str, str]],
    product_model: Optional[str] = None,
    software_update_timing: str = "",
    boot_or_screenshot_behavior: str = "",
    additional_customer_notes: str = "",
) -> Dict[str, Any]:
    normalized_answers = [item for item in answers if isinstance(item, dict) and str(item.get("answer", "")).strip()]
    if not normalized_answers:
        old_answers = [software_update_timing, boot_or_screenshot_behavior]
        for index, answer in enumerate(old_answers):
            if answer:
                question = (interview_state.get("questions") or [{}] * 2)[index]
                normalized_answers.append({
                    "question_id": question.get("question_id", f"q_{index + 1}"),
                    "question": question.get("question_text", "Customer follow-up"),
                    "answer": answer,
                })
        if additional_customer_notes:
            normalized_answers.append({"question_id": "customer_notes", "question": "Additional customer context", "answer": additional_customer_notes})
    return _case_agent.evaluate_answers(
        order_record=order_record,
        reported_symptom=reported_symptom,
        complaint_description=complaint_description,
        visual_observations=visual_observations,
        device_research=device_research,
        policy_assessment=policy_assessment,
        previous_interview=interview_state,
        answers=normalized_answers,
    )
