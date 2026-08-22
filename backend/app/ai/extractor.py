import re
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel

from app.retrieval.retriever import EvidenceRetriever, get_evidence_retriever
from app.retrieval.models import RetrievedEvidence
from app.ai.provider import AIProvider, get_ai_provider
from app.ai.schemas import MotorProtectionCircuitBreakerAttributes, ExtractedAttribute
from app.schemas.product import ProductAttribute, AttributeStatus
from app.normalization.dimension_parser import get_dimension_parser
from app.normalization.product_type_detector import get_product_type_detector
from app.reference_data.entity_masters import BRAND_ALIASES

logger = logging.getLogger(__name__)

MATERIAL_PATTERNS = [
    (r"\b(stainless steel|sst)\b", "Stainless Steel"),
    (r"\b(black stainless steel|bss)\b", "Black Stainless Steel"),
    (r"\b(aluminum|aluminium)\b", "Aluminum"),
    (r"\b(pvc|vinyl)\b", "PVC"),
    (r"\b(composite)\b", "Composite"),
    (r"\b(steel)\b", "Steel"),
    (r"\b(copper)\b", "Copper"),
    (r"\b(brass)\b", "Brass"),
    (r"\b(zinc)\b", "Zinc"),
]

COLOR_FINISH_PATTERNS = [
    (r"\b(black|bk|blk)\b", "Black", "Color"),
    (r"\b(white|wh)\b", "White", "Color"),
    (r"\b(nickel)\b", "Nickel", "Finish"),
    (r"\b(chrome|chromium)\b", "Chrome", "Finish"),
    (r"\b(brushed nickel)\b", "Brushed Nickel", "Finish"),
    (r"\b(oil rubbed bronze|orb)\b", "Oil Rubbed Bronze", "Finish"),
    (r"\b(polished brass)\b", "Polished Brass", "Finish"),
    (r"\b(ss|stainless)\b", "Stainless", "Finish"),
]

APPLICATION_PATTERNS = [
    (r"\bgeneral purpose\b", "General Purpose"),
    (r"\bmetal cut off\b", "Metal Cutting"),
    (r"\bwood cutting\b", "Wood Cutting"),
    (r"\bindoor\b", "Indoor"),
    (r"\boutdoor\b", "Outdoor"),
]

CONNECTION_PATTERNS = [
    (r"\b\d+\s*-\s*pole\b", "Pole Connection"),
    (r"\bd\.?ko\b", "DKO Arbor"),
    (r"\b\d+\s*mm\s*arbor\b", "Arbor Mount"),
]


class TextAttributeExtractor:
    """Deterministic regex-based extraction from product description/text."""

    def __init__(self):
        self.patterns = {
            "voltage": r"\b(\d+(?:\.\d+)?(?:\s*(?:-|–|—|/|to)\s*\d+(?:\.\d+)?)?\s*(?:V\s*AC|VAC|V\s*DC|VDC|Volts?|kV|V)\b(?:\s*(?:AC|DC))?)\b",
            "current": r"\b(\d+(?:\.\d+)?(?:\s*(?:-|–|—|/|to)\s*\d+(?:\.\d+)?)?\s*(?:Amps?|A|mA)\b)\b",
            "amperage": r"\b(\d+(?:\.\d+)?(?:\s*(?:-|–|—|/|to)\s*\d+(?:\.\d+)?)?\s*(?:Amps?|A|mA)\b)\b",
            "frequency": r"\b(\d+(?:/\d+)?\s*(?:Hz|hertz)\b)",
            "power": r"\b(\d+(?:\.\d+)?\s*(?:kW|kilowatts?|Watts?|W|HP|hp|horsepower)\b)",
            "pressure": r"\b(\d+(?:\.\d+)?\s*(?:psi|bar|Pa|kPa)\b)",
            "temperature": r"\b(-?\d+(?:\.\d+)?(?:\s*(?:to|-)\s*-?\d+(?:\.\d+)?)?\s*(?:°F|°C|deg\s*[FC]|F|C)\b)",
            "weight": r"\b(\d+(?:\.\d+)?\s*(?:lbs?|pounds?|kg|kilograms?|grams?|oz|ounces?))\b|\b(\d+(?:\.\d+)?\s+g)\b",
            "capacity": r"\b(\d+(?:\.\d+)?\s*(?:gal|gallons?|cu\.?\s*ft|cuft|liters?|litres?))\b|\b(\d+(?:\.\d+)?\s+l)\b",
            "rating": r"\b(\d+(?:\.\d+)?\s*(?:Watts?|W|HP|hp|Amps?|A)\b)",
            "poles": r"\b(\d+\s*(?:P|poles?)\b)",
            "grit": r"\b(P\d+|\d+\s*Grit|Grit\s*\d+|\b\d{2,4}\s*G\b)\b",
        }
        self.brand_patterns = sorted(
            set(BRAND_ALIASES.keys()) | {b.lower() for b in BRAND_ALIASES.values()},
            key=len,
            reverse=True,
        )
        self._dimension_parser = get_dimension_parser()
        self._product_type_detector = get_product_type_detector()

    def extract_candidate_facts(
        self,
        description: str,
        part_number: str = "",
        source_brand: str = "",
    ) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        if not description and not part_number:
            return facts

        text = f"{part_number} {description}".strip()
        seen: set = set()

        def add(name: str, value: str, source: str = "INPUT_DESCRIPTION", extra: Optional[Dict] = None):
            key = (name.lower(), value.lower())
            if key in seen or not value.strip():
                return
            seen.add(key)
            entry = {"name": name, "value": value.strip(), "source": source}
            if extra:
                entry.update(extra)
            facts.append(entry)

        # Dimension / quantity / grit / size parsing
        for item in self._dimension_parser.parse(description, part_number):
            add(item["name"], item["value"], item.get("source", "INPUT_DESCRIPTION"))

        # Electrical / physical patterns
        for attr_name, pattern in self.patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1) or match.group(2) if match.lastindex else match.group(0)
                if val:
                    add(attr_name, val.strip())

        # Material
        for pattern, material in MATERIAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                add("material", material)

        # Color / Finish
        for pattern, value, attr in COLOR_FINISH_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                add(attr.lower(), value)

        # Application / Connection / Mounting hints
        for pattern, value in APPLICATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                add("application", value)
        for pattern, value in CONNECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                add("connection", value)
        if re.search(r"\b(?:wall|ceiling|surface|panel)\s+mount", text, re.IGNORECASE):
            mount = re.search(r"\b((?:wall|ceiling|surface|panel)\s+mount)\b", text, re.IGNORECASE)
            if mount:
                add("mounting", mount.group(1).title())

        # Product type candidate
        type_result = self._product_type_detector.detect(description, part_number)
        if type_result.candidate_type:
            add(
                "product_type",
                type_result.candidate_type,
                extra={
                    "candidate_type": type_result.candidate_type,
                    "confidence": type_result.confidence,
                    "status": type_result.status.value,
                },
            )

        # Source brand (from input fields)
        if source_brand:
            add("source_brand", source_brand, source="INPUT_FIELD")

        # Description-derived brand candidates
        for b in self.brand_patterns:
            if re.search(r"\b" + re.escape(b) + r"\b", text, re.IGNORECASE):
                canonical = BRAND_ALIASES.get(b.lower(), b if b[0].isupper() else b.title())
                add("candidate_brand", canonical, source="INPUT_DESCRIPTION")
                add("brand", canonical, source="INPUT_DESCRIPTION")
                break

        # Model from part number prefix when description starts with MPN
        if part_number and description.upper().startswith(part_number.upper()):
            add("model", part_number, source="INPUT_FIELD")

        return facts


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
            f"Content:\n{item.text.strip()}\n"
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
        self.ai_provider = ai_provider or get_ai_provider()

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

        query_parts = [brand, part_number, category, description, "technical specifications voltage current frequency mounting poles dimensions standards"]
        search_query = " ".join(p for p in query_parts if p).strip()

        filter_criteria = {"product_id": product_id} if product_id else None
        retrieved_evidence = self.retriever.search(
            query=search_query,
            top_k=top_k,
            filter_criteria=filter_criteria
        )

        if not retrieved_evidence and filter_criteria:
            retrieved_evidence = self.retriever.search(query=search_query, top_k=top_k)

        qualified_evidence = [
            ev for ev in retrieved_evidence
            if ev.similarity_score >= min_similarity_threshold
        ]

        retrieved_map = {ev.evidence_id: ev for ev in qualified_evidence}

        if not qualified_evidence:
            logger.info("Insufficient evidence retrieved. Generating fallback attributes.")
            fallback_attributes = self._build_insufficient_evidence_fallback(schema)
            return {
                "attributes": fallback_attributes,
                "retrieved_evidence": [],
                "raw_extracted": None,
                "status": "INSUFFICIENT_EVIDENCE",
            }

        evidence_text = format_evidence_for_prompt(qualified_evidence)
        product_summary = f"Brand: {brand}\nPart Number: {part_number}\nCategory: {category}\nDescription: {description}"

        raw_result = self.ai_provider.extract_product_attributes(
            product_info=product_summary,
            evidence=evidence_text,
            schema=schema
        )

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

            valid_evidence_ids = [eid for eid in raw_evidence_ids if eid in retrieved_map]

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
                    avg_sim = sum(retrieved_map[eid].similarity_score for eid in valid_evidence_ids) / len(valid_evidence_ids)
                    confidence = round(min(1.0, max(0.5, avg_sim)), 2)
                    final_status = AttributeStatus.REQUIRES_REVIEW if (norm_res and norm_res.requires_review) else AttributeStatus.VERIFIED
                else:
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
