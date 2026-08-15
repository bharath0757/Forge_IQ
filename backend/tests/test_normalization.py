import pytest
from app.normalization.service import NormalizationService, get_normalization_service
from app.normalization.models import NormalizedAttributeResult


@pytest.fixture
def normalizer():
    return NormalizationService()


def test_voltage_normalization_variations(normalizer):
    """Test normalizing various voltage formats into canonical representation."""
    cases = [
        ("400 volts", "400 V", "V"),
        ("400V", "400 V", "V"),
        ("400 V AC", "400 V AC", "V"),
        ("230VAC", "230 V AC", "V"),
        ("24 VDC", "24 V DC", "V"),
        ("24V DC", "24 V DC", "V"),
        ("0.4 kV", "400 V", "V"),
        ("400/690 V", "400-690 V", "V"),
        ("110 - 230 V", "110-230 V", "V"),
    ]

    for raw, expected_norm, expected_unit in cases:
        res = normalizer.normalize_attribute("voltage", raw)
        assert res.raw_value == raw, f"raw_value was mutated for {raw}"
        assert res.normalized_value == expected_norm, f"Failed for {raw}: got {res.normalized_value}"
        assert res.unit == expected_unit, f"Wrong unit for {raw}: got {res.unit}"
        assert not res.requires_review


def test_current_normalization_variations(normalizer):
    """Test normalizing various current formats into canonical representation."""
    cases = [
        ("10 amps", "10 A", "A"),
        ("10A", "10 A", "A"),
        ("16 amperes", "16 A", "A"),
        ("0.28 to 0.4 A", "0.28-0.4 A", "A"),
        ("0.28 - 0.4 A", "0.28-0.4 A", "A"),
        ("0.28...0.4 A", "0.28-0.4 A", "A"),
        ("500 mA", "500 mA", "mA"),
    ]

    for raw, expected_norm, expected_unit in cases:
        res = normalizer.normalize_attribute("current", raw)
        assert res.raw_value == raw
        assert res.normalized_value == expected_norm
        assert res.unit == expected_unit
        assert not res.requires_review


def test_frequency_normalization_variations(normalizer):
    """Test normalizing various frequency formats."""
    cases = [
        ("50Hz", "50 Hz", "Hz"),
        ("50 Hz", "50 Hz", "Hz"),
        ("50/60 Hz", "50/60 Hz", "Hz"),
        ("50-60 Hz", "50/60 Hz", "Hz"),
        ("50 / 60 hertz", "50/60 Hz", "Hz"),
        ("60 Hertz", "60 Hz", "Hz"),
        ("50 to 60 Hz", "50/60 Hz", "Hz"),
    ]

    for raw, expected_norm, expected_unit in cases:
        res = normalizer.normalize_attribute("frequency", raw)
        assert res.raw_value == raw
        assert res.normalized_value == expected_norm
        assert res.unit == expected_unit
        assert not res.requires_review


def test_dimensions_normalization_variations(normalizer):
    """Test normalizing dimensions from mm, cm, and inches."""
    cases = [
        ("97 x 45 x 97 mm", "97 x 45 x 97 mm", "mm"),
        ("97mm x 45mm x 97mm", "97 x 45 x 97 mm", "mm"),
        ("9.7cm x 4.5cm x 9.7cm", "97 x 45 x 97 mm", "mm"),
        ("3.82 x 1.77 x 3.82 inches", "97 x 45 x 97 mm", "mm"),
        ("H 97 x W 45 x D 97 mm", "97 x 45 x 97 mm", "mm"),
    ]

    for raw, expected_norm, expected_unit in cases:
        res = normalizer.normalize_attribute("dimensions", raw)
        assert res.raw_value == raw
        assert res.normalized_value == expected_norm
        assert res.unit == expected_unit


def test_poles_and_trip_class_normalization(normalizer):
    """Test electrical poles and trip class normalization."""
    # Poles
    p1 = normalizer.normalize_attribute("poles", "3 poles")
    assert p1.normalized_value == 3
    assert p1.raw_value == "3 poles"

    p2 = normalizer.normalize_attribute("poles", "3P")
    assert p2.normalized_value == 3

    # Trip class
    tc1 = normalizer.normalize_attribute("trip_class", "Class 10")
    assert tc1.normalized_value == "Class 10"

    tc2 = normalizer.normalize_attribute("trip_class", "Trip Class 10A")
    assert tc2.normalized_value == "Class 10A"


def test_ambiguous_values_flagged_for_review_without_guessing(normalizer):
    """Test that ambiguous, contradictory, or unparseable formats are flagged without guessing."""
    ambiguous_inputs = [
        ("voltage", "approx 400 or maybe 230 V"),
        ("voltage", "custom varies by application"),
        ("current", "see technical manual for details"),
        ("frequency", "unknown / TBD"),
    ]

    for attr, raw in ambiguous_inputs:
        res = normalizer.normalize_attribute(attr, raw)
        assert res.raw_value == raw
        assert res.is_ambiguous is True
        assert res.requires_review is True
        assert res.normalized_value is None
        assert res.message is not None
