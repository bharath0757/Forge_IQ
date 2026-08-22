import pytest
from app.normalization.fraction_normalizer import FractionNormalizer
from app.normalization.uom_normalizer import UOMNormalizer
from app.normalization.entity_resolution import get_entity_resolution_service

def test_fraction_normalization():
    assert FractionNormalizer.normalize_string("0.5") == "1/2"
    assert FractionNormalizer.normalize_string("0.25") == "1/4"
    assert FractionNormalizer.normalize_string("0.75") == "3/4"
    assert FractionNormalizer.normalize_string("0.125") == "1/8"
    assert FractionNormalizer.normalize_string("1.5") == "1-1/2"
    assert FractionNormalizer.normalize_string("0.03125") == "1/32"
    
    # Non standard decimals should remain
    assert FractionNormalizer.normalize_string("0.33") == "0.33"
    
def test_uom_normalization():
    assert UOMNormalizer.normalize_value_and_unit("24in") == "24 in"
    assert UOMNormalizer.normalize_value_and_unit("50.25 in") == "50.25 in"
    assert UOMNormalizer.normalize_value_and_unit("100lbs") == "100 lb"
    assert UOMNormalizer.normalize_value_and_unit("1-1/4inch") == "1-1/4 in"
    assert UOMNormalizer.normalize_value_and_unit("120vdc") == "120 VDC"
    
def test_combined_fraction_and_uom():
    # Simulate the pipeline flow
    val = "50.25 in"
    val = FractionNormalizer.normalize_string(val)
    val = UOMNormalizer.normalize_value_and_unit(val)
    assert val == "50-1/4 in"

def test_entity_resolution_placeholders():
    resolver = get_entity_resolution_service()
    
    # Must be removed
    assert resolver.clean_brand("-- Unbranded --") is None
    assert resolver.clean_brand("-- No Unilog Brand --") is None
    assert resolver.clean_brand("-- No DIB Brand --") is None
    assert resolver.clean_brand("N/A") is None
    assert resolver.clean_brand("Unknown") is None
    
    # Keep real brands
    assert resolver.clean_brand("Siemens") == "Siemens"
