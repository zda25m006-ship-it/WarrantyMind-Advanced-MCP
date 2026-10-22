import json
import re
from typing import Any, Dict, List

from warrantymind.database import get_conn
from warrantymind.schemas import RetrievedClause
from warrantymind.mcp_servers.protocol import LocalFastMCPRegistry

policy_rag_mcp = LocalFastMCPRegistry(
    server_name="pixel-warranty-research",
    instructions="Lexical retrieval of internal case-handling guidance with official Google links attached when available. The system never decides warranty eligibility automatically.",
)


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


@policy_rag_mcp.tool(
    name="retrieve_pixel_warranty_guidance",
    description="Retrieves scoped internal warranty-handling guidance and attaches current official Google source links. Coverage always remains unverified until a human checks the applicable terms.",
    input_schema={
        "type": "object",
        "properties": {
            "order_record": {"type": "object"},
            "visual_observations": {"type": "object"},
            "query": {"type": "string"},
            "device_research": {"type": "object"},
        },
        "required": ["order_record", "visual_observations", "query"],
    },
)
def evaluate_warranty_and_hybrid_rag(
    order_record: Dict[str, Any],
    visual_observations: Dict[str, Any],
    query: str,
    device_research: Dict[str, Any] | None = None,
    reference_date: str = "",
) -> Dict[str, Any]:
    device_research = device_research or {}
    region = order_record.get("region", "IN")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM policy_clauses WHERE region = ?", (region,)).fetchall()
    conn.close()

    product_category = order_record.get("product_category", "")
    product_model = order_record.get("product_model", "")
    query_tokens = set(_tokens(" ".join([
        query,
        product_category,
        product_model,
        " ".join(visual_observations.get("observable_symptoms", [])),
    ])))
    candidates = []
    for row in rows:
        item = dict(row)
        scope = json.loads(item.get("product_scope_json") or "[]")
        if scope and product_category not in scope and product_model not in scope:
            continue
        doc_tokens = set(_tokens(f"{item['title']} {item['text']}"))
        score = len(query_tokens & doc_tokens)
        candidates.append((score, item))
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    retrieved = []
    for rank, (_score, item) in enumerate(candidates[:4], start=1):
        retrieved.append(RetrievedClause(
            clause_id=item["clause_id"],
            document_id=item["document_id"],
            title=item["title"],
            program_type=item["program_type"],
            text=item["text"],
            bm25_rank=None,
            dense_rank=None,
            rrf_score=0.0,
            rerank_score=float(max(0, _score)),
            is_dependency_expanded=False,
            depends_on=json.loads(item.get("depends_on_json") or "[]"),
            requires_physical_inspection=bool(item.get("requires_physical_inspection", 1)),
        ))

    warranty_research = device_research.get("warranty_research", {})
    official_sources = warranty_research.get("sources", [])
    if official_sources:
        explanation = (
            "Official Google pages were retrieved for human review. Search results and snippets are not a binding coverage decision; "
            "a support specialist must confirm that the current terms apply to this product, region, purchase channel, and purchase date."
        )
    else:
        explanation = (
            "No verified official Google warranty source is available in this case. Coverage, repair eligibility, and any fees remain undetermined; "
            "a support specialist must check the current terms for this product, region, purchase channel, and purchase date."
        )

    citations = [item["source_id"] for item in official_sources if item.get("source_id")]
    citations.extend(item.clause_id for item in retrieved)
    return {
        "standard_warranty_active": None,
        "standard_warranty_expiry": str(order_record.get("warranty_expiry") or "UNVERIFIED"),
        "eligible_special_programs": [],
        "preliminary_eligibility": "REQUIRES_OFFICIAL_POLICY_VERIFICATION",
        "retrieved_clauses": [item.model_dump() for item in retrieved],
        "official_sources": official_sources,
        "policy_explanation": explanation,
        "citations": citations,
        "entailment_verified": False,
        "decision_authority": "human_support_review_required",
    }
