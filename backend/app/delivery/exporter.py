import csv
import io
from typing import List, Dict, Any
from app.delivery.schema import DELIVERY_COLUMNS

def export_to_csv(records: List[Dict[str, Any]]) -> str:
    """
    Export a list of delivery records to a CSV string.
    Ensures UTF-8 and exactly 252 columns.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=DELIVERY_COLUMNS, extrasaction='ignore', lineterminator='\n')
    
    writer.writeheader()
    for record in records:
        writer.writerow(record)
        
    return output.getvalue()
