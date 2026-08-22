import csv
import os
from typing import List

# Load the actual supplied Delivery Format CSV header
DELIVERY_FORMAT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "data", "Unihack_ Expected Output - Delivery Format.csv")
DELIVERY_FORMAT_CSV = os.path.abspath(DELIVERY_FORMAT_CSV)

def load_canonical_schema() -> List[str]:
    with open(DELIVERY_FORMAT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
    assert len(header) == 252, f"Schema column count is {len(header)}, must be exactly 252"
    assert len(set(header)) == 252, "Schema contains duplicate column names"
    
    return header

DELIVERY_COLUMNS = load_canonical_schema()

def get_empty_delivery_record() -> dict:
    """Returns a dictionary with all 252 columns initialized to empty strings."""
    return {col: "" for col in DELIVERY_COLUMNS}
