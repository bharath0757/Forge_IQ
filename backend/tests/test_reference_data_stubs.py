import pytest
from app.reference_data.manufacturer_master import get_manufacturer_master
from app.reference_data.uom_repository import get_uom_repository
from app.reference_data.fraction_repository import get_fraction_repository
from app.reference_data.lov_repository import get_lov_repository
from app.reference_data.content_rules import get_content_rules_engine

def test_manufacturer_master_not_implemented():
    master = get_manufacturer_master()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        master.normalize_manufacturer("Siemens")
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        master.resolve_brand("SIRIUS")

def test_uom_repository_not_implemented():
    repo = get_uom_repository()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        repo.validate_uom("mm")
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        repo.standardize_uom("mm")

def test_fraction_repository_not_implemented():
    repo = get_fraction_repository()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        repo.convert_fraction_to_decimal("1/2")

def test_lov_repository_not_implemented():
    repo = get_lov_repository()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        repo.get_allowed_values("General", "Color")
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        repo.resolve_lov_candidate("General", "Color", "Red")

def test_content_rules_engine_not_implemented():
    engine = get_content_rules_engine()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        engine.construct_description("Short", {})
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        engine.validate_description("Short", "Test Description")
