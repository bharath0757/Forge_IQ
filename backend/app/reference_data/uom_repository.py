"""
UOM Reference Data Interface.
"""
from typing import Optional, Dict, Any

class UOMRepository:
    def __init__(self):
        # TODO: Load Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx
        pass

    def validate_uom(self, uom: str) -> bool:
        raise NotImplementedError("Reference data unavailable (Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx missing)")

    def standardize_uom(self, raw_uom: str) -> Dict[str, Any]:
        """
        Returns canonical form, aliases, and conversion.
        """
        raise NotImplementedError("Reference data unavailable (Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx missing)")

_repo = None
def get_uom_repository() -> UOMRepository:
    global _repo
    if _repo is None:
        _repo = UOMRepository()
    return _repo
