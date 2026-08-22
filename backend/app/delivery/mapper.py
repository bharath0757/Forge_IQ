from typing import Dict, Any
from app.models.product import ProductTwin
from app.delivery.schema import get_empty_delivery_record
from app.delivery.descriptions import DescriptionEngine

def map_product_to_delivery_record(product: ProductTwin) -> Dict[str, Any]:
    """
    Map a ProductTwin object to the canonical 252-column UniHack delivery format.
    Uses canonical ProductTwin fields directly.
    """
    record = get_empty_delivery_record()
    
    def _clean(val: Any) -> str:
        if not val:
            return ""
        s = str(val).strip()
        if s.lower() in ("none", "null", "n/a", "unclassified", "unknown", ""):
            return ""
        return s
    
    # 1. Product Identity
    record["SKU - MY_PART_NUMBER"] = _clean(product.id)
    record["Mfg_Part_Num"] = _clean(product.part_number)
    record["PART_NUMBER"] = _clean(product.part_number)
    record["MANUFACTURER_PART_NUMBER"] = _clean(product.part_number)
    record["Part_Manuf"] = _clean(getattr(product, "manufacturer", None) or product.brand)
    record["MANUFACTURER_NAME"] = _clean(getattr(product, "manufacturer", None) or product.brand)
    record["BRAND_NAME"] = _clean(product.brand)
    
    # GTIN / UPC / EAN
    record["UPC"] = "" # TODO if mapped in attributes
    record["EAN"] = ""
    record["GTIN"] = ""
    record["UNSPSC"] = ""
    record["Discontinued"] = "Yes" if product.status == "DISCONTINUED" else "No"
    
    # 2. Taxonomy (read directly from ProductTwin fields)
    record["Dept"] = _clean(getattr(product, "taxonomy_dept", None))
    record["Class"] = _clean(getattr(product, "taxonomy_class", None))
    record["Fine"] = _clean(getattr(product, "taxonomy_fine", None))
    record["Classpath"] = _clean(getattr(product, "taxonomy_classpath", None) or product.category)
    
    # 3. Descriptions (read directly from ProductTwin fields, fallback to engine)
    record["SHORT_DESC"] = _clean(getattr(product, "desc_short", None))
    record["LONG_DESC1"] = _clean(getattr(product, "desc_long", None))
    record["INVOICE_DESC"] = _clean(getattr(product, "desc_invoice", None))
    record["MOBILE_DESC"] = _clean(getattr(product, "desc_mobile", None))
    record["RETAIL_DESC"] = _clean(getattr(product, "desc_retail", None))
    record["MARKETING_DESCRIPTION"] = _clean(getattr(product, "desc_marketing", None))
    
    if not record["SHORT_DESC"]:
        engine = DescriptionEngine(product)
        record["SHORT_DESC"] = engine.build_short_description()
        record["LONG_DESC1"] = engine.build_long_description()
        record["INVOICE_DESC"] = engine.build_invoice_description()
        record["MOBILE_DESC"] = engine.build_mobile_description()
        record["RETAIL_DESC"] = engine.build_retail_description()
        record["MARKETING_DESCRIPTION"] = engine.build_marketing_description()
    
    attributes_dict = {attr.name.lower(): attr for attr in product.attributes}
    
    # 5. Dimensions & Weights
    dim_attr = attributes_dict.get("dimensions")
    if dim_attr and isinstance(dim_attr.normalized_value, str) and "x" in dim_attr.normalized_value.lower():
        parts = dim_attr.normalized_value.lower().split("x")
        if len(parts) >= 2:
            record["HEIGHT"] = parts[0].strip()
            record["WIDTH"] = parts[1].strip()
            # The schema doesn't have a DEPTH column? It has LENGTH, HEIGHT, WIDTH
            record["LENGTH"] = parts[2].strip().split(" ")[0] if len(parts) >= 3 else ""
            record["LENGTH_UOM"] = dim_attr.unit or ""
            record["HEIGHT_UOM"] = dim_attr.unit or ""
            record["WIDTH_UOM"] = dim_attr.unit or ""
            
    weight_attr = attributes_dict.get("weight")
    if weight_attr:
        record["WEIGHT"] = weight_attr.normalized_value or weight_attr.value or ""
        record["WEIGHT_UOM"] = weight_attr.unit or ""
        
    # Map Attributes 1-50
    sorted_attrs = sorted(
        [a for a in product.attributes if a.name.lower() not in ["dimensions", "weight"]],
        key=lambda x: x.name
    )
    
    for i, attr in enumerate(sorted_attrs[:50]):
        idx = i + 1
        record[f"ATTRIBUTE_LABEL {idx}"] = _clean(attr.name)
        record[f"ATTRIBUTE_VALUE {idx}"] = _clean(attr.normalized_value or attr.value)
        record[f"ATTRIBUTE_UOM {idx}"] = _clean(attr.unit)
        
    return record
