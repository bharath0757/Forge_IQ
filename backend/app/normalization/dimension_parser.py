"""
Robust dimension and quantity parsing from product descriptions.
Preserves original expressions; normalizes via fraction/UOM layers.
"""
import re
from typing import Any, Dict, List, Optional

from app.normalization.fraction_normalizer import FractionNormalizer
from app.normalization.uom_normalizer import UOMNormalizer


# Numeric token: whole, fraction, mixed fraction, decimal
NUM = r"(?:\d+(?:-\d+/\d+|\d+/\d+|\.\d+)?|\d+)"

# Dimension chain patterns — ordered specific-first
DIMENSION_PATTERNS: List[tuple] = [
    # 1/2"x18", 7/8"x6-16', 4-1/2"x.045"x7/8"
    (rf'({NUM})\s*["\u2033]?\s*[xX×]\s*({NUM})\s*[-\']?(?:\d+\s*["\u2033]?)?(?:\s*[xX×]\s*({NUM}))?', "dimension_chain"),
    # 6'x36", 1x6-16'
    (rf"({NUM})\s*['\u2032]\s*[xX×]\s*({NUM})\s*[\"'\u2033]?", "feet_by_inches"),
    (rf"({NUM})\s*[xX×]\s*({NUM})\s*[-\']?\d*\s*['\u2032]", "lumber_length"),
    # 4x4, 1x6
    (rf"\b({NUM})\s*[xX×]\s*({NUM})\b(?!\s*(?:pc|pack|box|disc))", "size_cross"),
    # standalone 1-1/2", 7/8"
    (rf'\b({NUM})\s*["\u2033]\b', "diameter_or_thickness"),
    (rf"\b({NUM})\s*['\u2032]\b", "length_feet"),
]

QUANTITY_PATTERNS: List[tuple] = [
    (r"\b(\d+)\s*(?:pc|pcs|pk|pack|piece|pieces)\b", "count"),
    (r"\b(\d+)\s*disc\s*/\s*box\b", "disc_per_box"),
    (r"\b(\d+)\s*pack\b", "pack"),
    (r"\b(\d+)\s*box\b", "box"),
    (r"\b(?:case|box)\s*of\s*(\d+)\b", "case_count"),
    (r"\b(\d+)\s*case\b", "case"),
]

GRIT_PATTERN = r"\b(P\d+|\d+\s*Grit|Grit\s*\d+)\b"
SERIES_PATTERN = r"\b(?:series|ser\.?)\s*([A-Z0-9\-]+)\b"
MODEL_PATTERN = r"\b(?:model|mdl\.?)\s*#?\s*([A-Z0-9\-/]+)\b"


class DimensionParser:
    """Extract dimensions, quantities, and related sizing attributes."""

    def __init__(self):
        self._frac = FractionNormalizer
        self._uom = UOMNormalizer

    def _normalize_measure(self, raw: str, default_unit: str = "in") -> str:
        val = raw.strip().strip('"').strip("'")
        if not val:
            return raw
        if not re.search(r"[a-zA-Z\"'\u2032\u2033]", val):
            val = f"{val} {default_unit}"
        val = self._frac.normalize_string(val)
        return self._uom.normalize_value_and_unit(val)

    def parse(self, description: str, part_number: str = "") -> List[Dict[str, Any]]:
        text = f"{part_number} {description}".strip()
        if not text:
            return []

        facts: List[Dict[str, Any]] = []
        seen_values: set = set()

        def add_fact(name: str, raw: str, kind: str):
            if raw.lower() in seen_values:
                return
            seen_values.add(raw.lower())
            normalized = self._normalize_measure(raw) if "quantity" not in name else raw.strip()
            facts.append({
                "name": name,
                "value": raw.strip(),
                "normalized_value": normalized,
                "source": "INPUT_DESCRIPTION",
                "parse_kind": kind,
            })

        for pattern, kind in DIMENSION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw = match.group(0).strip()
                # Skip grit-like patterns (5"xP80)
                if re.search(r"P\d+", raw, re.IGNORECASE):
                    continue
                # Skip model/part number cross patterns at start of string
                if kind == "size_cross" and match.start() < 5 and part_number:
                    pn_prefix = part_number.split()[0] if part_number else ""
                    if pn_prefix and raw.replace(" ", "").startswith(pn_prefix[:3]):
                        continue

                if kind == "dimension_chain":
                    parts = [g for g in match.groups() if g]
                    if len(parts) == 2:
                        add_fact("width", parts[0] + '"', kind)
                        add_fact("length", parts[1] + '"', kind)
                    elif len(parts) >= 3:
                        add_fact("width", parts[0] + '"', kind)
                        add_fact("thickness", parts[1], kind)
                        add_fact("diameter", parts[2] + '"', kind)
                    add_fact("dimensions", raw, kind)
                elif kind == "feet_by_inches":
                    add_fact("length", match.group(1) + "'", kind)
                    add_fact("width", match.group(2) + '"', kind)
                    add_fact("dimensions", raw, kind)
                elif kind == "lumber_length":
                    add_fact("size", raw, kind)
                    add_fact("length", match.group(0).split("x")[-1].strip(), kind)
                elif kind == "size_cross":
                    add_fact("size", raw, kind)
                    add_fact("width", match.group(1), kind)
                    add_fact("height", match.group(2), kind)
                elif kind == "diameter_or_thickness":
                    # Heuristic: small fractions often diameter in abrasives
                    add_fact("diameter", raw, kind)
                    add_fact("thickness", raw, kind)
                elif kind == "length_feet":
                    add_fact("length", raw, kind)

        for pattern, kind in QUANTITY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                add_fact("quantity", match.group(0).strip(), kind)

        for match in re.finditer(GRIT_PATTERN, text, re.IGNORECASE):
            add_fact("grit", match.group(0).strip(), "grit")

        for match in re.finditer(SERIES_PATTERN, text, re.IGNORECASE):
            add_fact("series", match.group(1).strip(), "series")

        for match in re.finditer(MODEL_PATTERN, text, re.IGNORECASE):
            add_fact("model", match.group(1).strip(), "model")

        return facts


_default_parser: Optional[DimensionParser] = None


def get_dimension_parser() -> DimensionParser:
    global _default_parser
    if _default_parser is None:
        _default_parser = DimensionParser()
    return _default_parser
