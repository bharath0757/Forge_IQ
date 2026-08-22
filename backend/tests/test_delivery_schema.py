import pytest
from app.delivery.schema import DELIVERY_COLUMNS, get_empty_delivery_record
from app.delivery.mapper import map_product_to_delivery_record
from app.delivery.exporter import export_to_csv
from app.models.product import ProductTwin, ProductAttribute

def test_exactly_252_columns():
    assert len(DELIVERY_COLUMNS) == 252, f"Expected 252 columns, got {len(DELIVERY_COLUMNS)}"

def test_no_duplicate_column_names():
    duplicates = [item for item in set(DELIVERY_COLUMNS) if DELIVERY_COLUMNS.count(item) > 1]
    assert not duplicates, f"Found duplicate columns: {duplicates}"

def test_csv_exporter_produces_exact_columns():
    record = get_empty_delivery_record()
    record[DELIVERY_COLUMNS[0]] = "test1234"
    
    csv_str = export_to_csv([record])
    header_line = csv_str.split("\n")[0]
    exported_columns = header_line.split(",")
    
    assert len(exported_columns) == 252
    assert exported_columns[0] == DELIVERY_COLUMNS[0]

def test_mapper_never_silently_adds_removes_columns():
    prod = ProductTwin(
        id="prod_01",
        part_number="ABC-123",
        brand="ACME",
        description="A great product"
    )
    prod.attributes = [
        ProductAttribute(name="voltage", value="10", normalized_value="10 V", unit="V"),
        ProductAttribute(name="current", value="5A", normalized_value="5 A", unit="A"),
    ]
    
    mapped = map_product_to_delivery_record(prod)
    
    # Check that all keys in mapped are in DELIVERY_COLUMNS
    for key in mapped.keys():
        assert key in DELIVERY_COLUMNS, f"Key {key} not in DELIVERY_COLUMNS"
        
    # Check that all keys in DELIVERY_COLUMNS are in mapped
    for col in DELIVERY_COLUMNS:
        assert col in mapped, f"Column {col} missing from mapped output"
