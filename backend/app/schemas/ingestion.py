from pydantic import BaseModel
from typing import Optional

class ProductIngestRequest(BaseModel):
    part_number: str
    brand: str
    description: str
    category: Optional[str] = "General"
