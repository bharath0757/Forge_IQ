import pytest
from app.delivery.descriptions import DescriptionEngine
from app.models.product import ProductTwin, ProductAttribute

def test_description_engine_limits_and_formats():
    prod = ProductTwin(
        id="prod_desc",
        part_number="XYZ-987",
        brand="IndustrialCorp",
        description="This is a very very long raw description that should be used for retail and marketing purposes because it contains a lot of fluff.",
        category="Valves"
    )
    prod.attributes = [
        ProductAttribute(name="size", value="2 in", normalized_value="2 in", unit="in"),
        ProductAttribute(name="pressure", value="150 psi", normalized_value="150 psi", unit="psi"),
    ]
    
    engine = DescriptionEngine(prod)
    
    short = engine.build_short_description()
    assert len(short) <= 120
    assert "IndustrialCorp" in short
    assert "XYZ-987" in short
    assert "2 in" in short
    
    invoice = engine.build_invoice_description()
    assert len(invoice) <= 60
    assert invoice == invoice.upper()
    assert "XYZ-987" in invoice
    
    long_desc = engine.build_long_description()
    assert len(long_desc) <= 500
    assert "Specifications" in long_desc
    assert "Size: 2 in" in long_desc
    assert "Pressure: 150 psi" in long_desc
    
    retail = engine.build_retail_description()
    assert "fluff" in retail # Should fall back to the raw long description
