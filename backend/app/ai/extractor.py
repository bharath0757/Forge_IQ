import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel

from app.retrieval.retriever import EvidenceRetriever, get_evidence_retriever
from app.retrieval.models import RetrievedEvidence
from app.ai.provider import AIProvider, LangchainOpenAIProvider
from app.ai.schemas import MotorProtectionCircuitBreakerAttributes, ExtractedAttribute
from app.schemas.product import ProductAttribute, AttributeStatus

logger = logging.getLogger(__name__)


def format_evidence_for_prompt(evidence_list: List[RetrievedEvidence]) -> str:
    """Format retrieved evidence items into a clean structured string for LLM prompts."""
    if not evidence_list:
        return "No relevant evidence documents found."

    formatted_blocks = []
    for item in evidence_list:
        page_str = f"Page {item.page_number}" if item.page_number else "Page N/A"
        block = (
            f"[Evidence ID: {item.evidence_id}]\n"
            f"Document: {item.document_name} ({page_str}, Chunk #{item.chunk_index})\n"
            f"Similarity Score: {item.similarity_score:.4f}\n"
            f"Snippet:\n{item.text.strip()}\n"
            f"---"
        )
        formatted_blocks.append(block)

    return "\n\n".join(formatted_blocks)


class ProductAttributeExtractor:
    """
    Coordinates evidence retrieval and structured LLM extraction.
    Retrieves top-k evidence first and provides only relevant grounded context to the LLM.
    """

    def __init__(
        self,
        retriever: Optional[EvidenceRetriever] = None,
        ai_provider: Optional[AIProvider] = None,
    ):
        self.retriever = retriever or get_evidence_retriever()
        self.ai_provider = ai_provider or LangchainOpenAIProvider()

    def extract(
        self,
        product_info: Dict[str, Any],
        top_k: int = 5,
        min_similarity_threshold: float = 0.05,
        schema: Type[BaseModel] = MotorProtectionCircuitBreakerAttributes,
    ) -> Dict[str, Any]:
        """
        1. Formulate search query from product info.
        2. Retrieve top-k relevant evidence from the vector storage.
        3. If evidence is insufficient, fallback to UNKNOWN/REQUIRES_REVIEW attributes.
        4. If evidence is present, format retrieved chunks and invoke LLM.
        5. Build and validate final ProductAttribute records with attached evidence IDs.
        """
        part_number = product_info.get("part_number", "")
        brand = product_info.get("brand", "")
        category = product_info.get("category", "")
        description = product_info.get("description", "")
        product_id = product_info.get("id")

        # 1. Build targeted query
        query_parts = [brand, part_number, category, description, "technical specifications voltage current frequency mounting poles dimensions standards"]
        search_query = " ".join(p for p in query_parts if p).strip()

        # 2. Retrieve top-k evidence
        filter_criteria = {"product_id": product_id} if product_id else None
        retrieved_evidence = self.retriever.search(
            query=search_query,
            top_k=top_k,
            filter_criteria=filter_criteria
        )

        # If product_id filter yielded no results, try searching globally without filter
        if not retrieved_evidence and filter_criteria:
            retrieved_evidence = self.retriever.search(query=search_query, top_k=top_k)

        # Filter out items with very low similarity
        qualified_evidence = [
            ev for ev in retrieved_evidence
            if ev.similarity_score >= min_similarity_threshold
        ]

        retrieved_map = {ev.evidence_id: ev for ev in qualified_evidence}

        # 3. Check for insufficient evidence
        if not qualified_evidence:
            logger.info("Insufficient evidence retrieved. Generating fallback attributes.")
            fallback_attributes = self._build_insufficient_evidence_fallback(schema)
            return {
                "attributes": fallback_attributes,
                "retrieved_evidence": [],
                "raw_extracted": None,
                "status": "INSUFFICIENT_EVIDENCE",
            }

        # 4. Format evidence and invoke AI Provider
        evidence_text = format_evidence_for_prompt(qualified_evidence)
        product_summary = f"Brand: {brand}\nPart Number: {part_number}\nCategory: {category}\nDescription: {description}"

        raw_result = self.ai_provider.extract_product_attributes(
            product_info=product_summary,
            evidence=evidence_text,
            schema=schema
        )

        # 5. Transform and validate extracted attributes with evidence IDs
        final_attributes = self._process_extracted_schema(raw_result, retrieved_map)

        return {
            "attributes": final_attributes,
            "retrieved_evidence": qualified_evidence,
            "raw_extracted": raw_result,
            "status": "SUCCESS",
        }

    def _process_extracted_schema(
        self,
        extracted: BaseModel,
        retrieved_map: Dict[str, RetrievedEvidence]
    ) -> List[ProductAttribute]:
        """Convert Pydantic extracted fields into validated ProductAttribute models."""
        attributes: List[ProductAttribute] = []

        for field_name, value_obj in extracted:
            if not isinstance(value_obj, ExtractedAttribute):
                continue

            attr_value = value_obj.value
            status_str = value_obj.status.upper()
            raw_evidence_ids = value_obj.evidence_ids or []

            # Verify evidence IDs against actually retrieved evidence
            valid_evidence_ids = [eid for eid in raw_evidence_ids if eid in retrieved_map]

            # Perform canonical normalization while preserving raw_value
            norm_res = None
            normalized_value = None
            unit = None

            if attr_value is not None:
                from app.normalization.service import get_normalization_service
                normalizer = get_normalization_service()
                norm_res = normalizer.normalize_attribute(field_name, attr_value)
                normalized_value = norm_res.normalized_value
                unit = norm_res.unit

            if status_str == "EXTRACTED" and attr_value is not None:
                if valid_evidence_ids:
                    # Confidence derived from average similarity of supporting evidence
                    avg_sim = sum(retrieved_map[eid].similarity_score for eid in valid_evidence_ids) / len(valid_evidence_ids)
                    confidence = round(min(1.0, max(0.5, avg_sim)), 2)
                    final_status = AttributeStatus.REQUIRES_REVIEW if (norm_res and norm_res.requires_review) else AttributeStatus.VERIFIED
                else:
                    # Extracted without valid evidence grounding -> mark REQUIRES_REVIEW
                    confidence = 0.4
                    final_status = AttributeStatus.REQUIRES_REVIEW
                    valid_evidence_ids = list(retrieved_map.keys())[:1] if retrieved_map else []
            elif status_str in ("REQUIRES_REVIEW", "UNVERIFIED"):
                confidence = 0.5
                final_status = AttributeStatus.REQUIRES_REVIEW
            else:
                attr_value = None
                normalized_value = None
                unit = None
                confidence = 0.0
                final_status = AttributeStatus.UNKNOWN
                valid_evidence_ids = []

            attributes.append(
                ProductAttribute(
                    name=field_name,
                    value=attr_value,
                    normalized_value=normalized_value,
                    unit=unit,
                    confidence=confidence,
                    status=final_status,
                    evidence_ids=valid_evidence_ids,
                    conflict_ids=[],
                )
            )

        return attributes

    def _build_insufficient_evidence_fallback(
        self,
        schema: Type[BaseModel]
    ) -> List[ProductAttribute]:
        """Produce fallback attributes marked as UNKNOWN when evidence is lacking."""
        attributes: List[ProductAttribute] = []
        for field_name in schema.model_fields.keys():
            attributes.append(
                ProductAttribute(
                    name=field_name,
                    value=None,
                    confidence=0.0,
                    status=AttributeStatus.UNKNOWN,
                    evidence_ids=[],
                    conflict_ids=[],
                )
            )
        return attributes
