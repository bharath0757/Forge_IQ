"""
Manufacturer and Brand Master Reference Interface.
Provides canonical normalization and mapping.
"""

from typing import Optional, Dict, Any

class ManufacturerMaster:
    def __init__(self):
        # TODO: Load Unicat_Manufacturer_and_Brand_List.xlsx when available
        pass

    def normalize_manufacturer(self, raw_input: str) -> Dict[str, Any]:
        """
        Normalizes raw manufacturer input against the master list.
        Returns match type, confidence, and canonical code.
        """
        raise NotImplementedError("Reference data unavailable (Unicat_Manufacturer_and_Brand_List.xlsx missing)")

    def resolve_brand(self, raw_brand: str, manufacturer: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves brand to its canonical paired manufacturer.
        """
        raise NotImplementedError("Reference data unavailable (Unicat_Manufacturer_and_Brand_List.xlsx missing)")

# Singleton instance
_master = None

def get_manufacturer_master() -> ManufacturerMaster:
    global _master
    if _master is None:
        _master = ManufacturerMaster()
    return _master
