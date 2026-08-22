"""
ForgeIQ Description Engine
Deterministic rule-based description builder.
Generates 6 canonical descriptions and validates them against rules.
"""
import re
from typing import Dict, List, Any
from app.models.product import ProductTwin

class DescriptionEngine:
    """
    Deterministic rule-based description builder.
    Does NOT use LLMs to invent text. Only builds descriptions from canonical facts.
    """
    def __init__(self, product: ProductTwin):
        self.product = product
        self.attributes = {attr.name.lower(): attr for attr in (product.attributes or [])}
        raw_b = product.brand or ""
        self.brand = raw_b if self._is_valid(raw_b) else ""
        raw_m = getattr(product, 'manufacturer', None) or ""
        self.manufacturer = raw_m if self._is_valid(raw_m) else ""
        raw_p = product.part_number or ""
        self.mpn = raw_p if self._is_valid(raw_p) else ""
        self.raw_desc = product.description or ""
        
        # Category resolution
        self.category = ""
        product_type_attr = self.attributes.get("product_type") or self.attributes.get("candidate_type")
        if product_type_attr:
            pt_val = product_type_attr.normalized_value or product_type_attr.value
            if self._is_valid(str(pt_val)):
                self.category = str(pt_val)
        
        if not self.category:
            fine = getattr(product, 'taxonomy_fine', None)
            if fine and self._is_valid(fine) and fine.lower() != "unclassified":
                self.category = fine
            elif product.category and self._is_valid(product.category) and product.category.lower() != "unclassified":
                # Use fine category if it's a classpath
                if ">" in product.category:
                    self.category = product.category.split(">")[-1].strip()
                else:
                    self.category = product.category

    def _is_valid(self, text: str) -> bool:
        if not text:
            return False
        t = str(text).strip().lower()
        if t in ("unclassified", "unknown", "none", "n/a", "na", "not available", "null", "-", "--", "."):
            return False
        if re.search(r'\b(unclassified|unknown|none)\b', t):
            return False
        return True

    def _get_val(self, key: str) -> str:
        attr = self.attributes.get(key.lower())
        if not attr:
            return ""
        val = attr.normalized_value if attr.normalized_value is not None else attr.value
        if val is None:
            return ""
        s_val = str(val).strip()
        if not self._is_valid(s_val):
            return ""
        return f"{s_val} {attr.unit}".strip() if attr.unit and not s_val.endswith(attr.unit) else s_val

    def _get_key_specs(self) -> List[str]:
        specs = []
        for k in ["dimensions", "size", "grit", "voltage", "current", "power", "weight", "poles", "material", "finish", "color", "quantity"]:
            val = self._get_val(k)
            if val and val not in specs:
                specs.append(val)
        if not specs and self.product.attributes:
            for attr in self.product.attributes:
                if attr.name.lower() not in ["dept", "class", "fine", "classpath", "product_type", "candidate_type", "candidate_brand", "source_brand"]:
                    val = self._get_val(attr.name)
                    if val and val not in specs:
                        specs.append(val)
        return specs

    def build_short_description(self) -> str:
        """Usually: Brand + MPN + Core Category + 1-2 Key Specs. Limit 120 chars."""
        parts = [p for p in [self.brand, self.mpn, self.category] if self._is_valid(p)]
        specs = self._get_key_specs()[:2]
        for s in specs:
            if s and s.lower() not in [p.lower() for p in parts]:
                parts.append(s)
        desc = " - ".join(parts).strip() if parts else (self.raw_desc[:120] if self._is_valid(self.raw_desc) else "")
        return desc[:120]

    def build_long_description(self) -> str:
        """Detailed description combining all verified attributes. Limit 1000 chars."""
        parts = [p for p in [self.brand, self.mpn] if self._is_valid(p)]
        base = " ".join(parts).strip()
        if self._is_valid(self.category):
            base = f"{base} is a {self.category}." if base else f"{self.category}."
        elif base:
            base += "."
            
        specs = []
        if self.product.attributes:
            for attr in self.product.attributes:
                if attr.name.lower() in ["dept", "class", "fine", "classpath", "product_type", "candidate_type", "source_brand"]:
                    continue
                val = attr.normalized_value if attr.normalized_value is not None else attr.value
                if val is not None:
                    unit = f" {attr.unit}" if attr.unit and not str(val).endswith(attr.unit) else ""
                    val_str = f"{val}{unit}".strip()
                    if self._is_valid(val_str):
                        specs.append(f"{attr.name.replace('_', ' ').title()}: {val_str}")
        
        desc = base
        if specs:
            spec_text = "Specifications: " + ", ".join(specs) + "."
            desc = f"{desc} {spec_text}".strip() if desc else spec_text
        if not desc:
            desc = self.raw_desc[:1000] if self._is_valid(self.raw_desc) else ""
        return desc[:1000]

    def build_invoice_description(self) -> str:
        """Concise, UPPERCASE, limit 60 chars."""
        cat = (self.category or "").split(" ")[0]
        parts = [p for p in [self.brand, self.mpn, cat] if self._is_valid(p)]
        desc = " ".join(parts).strip().upper()
        if not desc and self._is_valid(self.raw_desc):
            desc = self.raw_desc[:60].upper()
        desc = re.sub(r'\s+', ' ', desc)
        return desc[:60]

    def build_mobile_description(self) -> str:
        """Very short, scannable, limit 80 chars."""
        parts = [p for p in [self.brand, self.mpn, self.category] if self._is_valid(p)]
        desc = " ".join(parts).strip()
        if not desc:
            desc = self.build_short_description()[:80]
        return desc[:80]

    def build_retail_description(self) -> str:
        """Retail focused, uses cleaned raw desc if suitable, else long desc."""
        if self.raw_desc and len(self.raw_desc) > 10 and self._is_valid(self.raw_desc):
            cleaned = re.sub(r'\s+', ' ', self.raw_desc).strip()
            return cleaned[:500]
        return self.build_long_description()[:500]

    def build_marketing_description(self) -> str:
        """Marketing focused, highlights manufacturer and key features."""
        base = self.build_retail_description()
        features = []
        if self._get_val("efficiency"):
            features.append(f"High efficiency ({self._get_val('efficiency')})")
        if self._get_val("protection"):
            features.append(f"Rugged design ({self._get_val('protection')})")
        if self._get_val("certification"):
            features.append(f"Certified ({self._get_val('certification')})")
        
        feature_text = " Features include: " + ", ".join(features) + "." if features else ""
        
        subj = f"{self.brand} {self.mpn}".strip()
        if subj:
            target_cat = self.category.lower() if self.category else "industrial and commercial"
            marketing_text = f"The {subj} delivers reliable performance for {target_cat} applications."
            full_desc = f"{marketing_text} {base}{feature_text}"
        else:
            full_desc = f"{base}{feature_text}"
        
        full_desc = re.sub(r'\s+', ' ', full_desc).strip()
        return full_desc[:800]

    def validate_descriptions(self) -> Dict[str, Any]:
        """Validate all descriptions against rules."""
        short_d = self.build_short_description()
        long_d = self.build_long_description()
        inv_d = self.build_invoice_description()
        mob_d = self.build_mobile_description()
        ret_d = self.build_retail_description()
        mkt_d = self.build_marketing_description()

        results = {
            "short": len(short_d) <= 120 and self._is_valid(short_d),
            "long": len(long_d) <= 1000 and self._is_valid(long_d),
            "invoice": len(inv_d) <= 60 and (inv_d.isupper() or not inv_d),
            "mobile": len(mob_d) <= 80 and self._is_valid(mob_d),
            "retail": len(ret_d) > 0 and self._is_valid(ret_d),
            "marketing": len(mkt_d) > 0 and self._is_valid(mkt_d),
        }
        return {
            "all_passed": all(results.values()),
            "details": results
        }
