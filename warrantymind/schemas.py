from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel as _PydanticBaseModel, Field


class BaseModel(_PydanticBaseModel):
    def model_dump(self, *args, **kwargs):
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)


class VisualObservationResult(BaseModel):
    vlm_status: Literal["not_attempted", "available", "unavailable", "error"] = "not_attempted"
    analysis_mode: Literal["complaint_text_fallback", "ollama_vision"] = "complaint_text_fallback"
    product_relevance: Literal["consistent", "inconsistent", "uncertain"] = "uncertain"
    image_quality: Literal["usable", "blurry_or_glare", "missing", "uncertain"] = "uncertain"
    observable_symptoms: List[str] = Field(default_factory=list)
    visible_external_damage: Literal["none_visible", "cracked_glass", "chassis_dent", "liquid_corrosion_visible", "uncertain"] = "none_visible"
    vlm_Direct_customer_feedback: str = ""
    vlm_suspected_origin: Literal[
        "spontaneous_oled_or_post_update_driver_issue",
        "software_compositor_or_firmware_glitch",
        "external_physical_impact_or_crush",
        "thermal_or_power_delivery_degradation",
        "needs_more_visual_or_symptom_context"
    ] = "spontaneous_oled_or_post_update_driver_issue"
    vlm_suspicion_reasoning: str = ""
    pixel_inspection_telemetry: Dict[str, Any] = Field(default_factory=dict)
    internal_or_liquid_cause: Literal["cannot_verify_remotely"] = "cannot_verify_remotely"
    identity_serial_status: Literal["verified_from_label", "unverified_pending_inspection"] = "unverified_pending_inspection"
    confidence_note: str = ""
    requested_additional_views: List[str] = Field(default_factory=list)


class DiagnosticQuestionItem(BaseModel):
    question_id: str
    topic: str
    question_text: str
    why_asking: str
    suggested_quick_answers: List[str] = Field(default_factory=list)


class DiagnosticInterviewState(BaseModel):
    status: Literal["awaiting_customer_answers", "completed"] = "awaiting_customer_answers"
    agent_status: str = "ready"
    agent_model: Optional[str] = None
    agent_opening_message: str
    customer_response: str = ""
    questions: List[DiagnosticQuestionItem] = Field(default_factory=list)
    customer_answers: List[Dict[str, str]] = Field(default_factory=list)
    refined_diagnosis_hypothesis: Optional[str] = None
    software_vs_hardware_conclusion: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "low"
    source_citations: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    recommended_troubleshooting_steps: List[str] = Field(default_factory=list)


class InvoiceExtractionResult(BaseModel):
    invoice_number: Optional[str] = None
    extracted_model: Optional[str] = None
    extracted_serial: Optional[str] = None
    purchase_date: Optional[str] = None
    vendor_name: Optional[str] = None
    verification_status: Literal["matched_order_db", "mismatch_flagged", "no_invoice_uploaded_using_order_db"] = "no_invoice_uploaded_using_order_db"


class RetrievedClause(BaseModel):
    clause_id: str
    document_id: str
    title: str
    program_type: str
    text: str
    bm25_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    is_dependency_expanded: bool = False
    depends_on: List[str] = Field(default_factory=list)
    requires_physical_inspection: bool = True


class PolicyAssessmentResult(BaseModel):
    standard_warranty_active: Optional[bool] = None
    standard_warranty_expiry: str
    eligible_special_programs: List[str] = Field(default_factory=list)
    preliminary_eligibility: str = "REQUIRES_OFFICIAL_POLICY_VERIFICATION"
    retrieved_clauses: List[RetrievedClause] = Field(default_factory=list)
    policy_explanation: str
    citations: List[str] = Field(default_factory=list)
    official_sources: List[Dict[str, Any]] = Field(default_factory=list)
    decision_authority: str = "human_support_review_required"
    entailment_verified: bool = False


class PriceEstimateScenario(BaseModel):
    component_code: str
    component_name: str
    diagnostic_fee_inr: int
    repair_min_inr: int
    repair_max_inr: int
    covered_if_inspection_passes: bool
    catalog_version: str = "CAT-2026-Q4"
    notes: str = ""


class DiagnosticInterviewReplyRequest(BaseModel):
    software_update_timing: Optional[str] = ""
    boot_or_screenshot_behavior: Optional[str] = ""
    additional_customer_notes: Optional[str] = ""
    answers: List[Dict[str, str]] = Field(default_factory=list)


class TechnicianInspectionInput(BaseModel):
    serial_verified: bool = True
    physical_impact_damage: bool = False
    liquid_contact_detected: bool = False
    confirmed_fault_component: Literal["display_module", "battery_subsystem", "logic_board", "enclosure_glass", "no_fault_found"] = "display_module"
    technician_notes: str


class SlotConsentRequest(BaseModel):
    slot_id: str
    quote_version: str
    customer_consent_accepted: bool


class RepairOfferConsentRequest(BaseModel):
    repair_consent_accepted: bool
    customer_comment: Optional[str] = None


class EscalationRequest(BaseModel):
    reason: str
    customer_message: str


class SupportReplyRequest(BaseModel):
    message: str
    resolution_action: Optional[Literal["keep_inspection_requirement", "waive_diagnostic_fee", "priority_slot_override"]] = None
