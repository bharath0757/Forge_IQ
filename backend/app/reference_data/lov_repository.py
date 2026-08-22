"""
LOV (List of Values) Reference Interface.
"""
from typing import Optional, Dict, Any, List

class LOVRepository:
    def __init__(self):
        # TODO: Load Unicat_Lov_v1_0_Updated_With_Remarks.xlsx, FAUCETS_LOV.xlsx, Fittings_LOV.xlsx
        pass

    def get_allowed_values(self, category: str, attribute_label: str) -> List[str]:
        raise NotImplementedError("Reference data unavailable (LOV excel files missing)")

    def resolve_lov_candidate(self, category: str, attribute_label: str, raw_candidate: str) -> Dict[str, Any]:
        """
        Resolves candidate to LOV canonical value.
        """
        raise NotImplementedError("Reference data unavailable (LOV excel files missing)")

_repo = None
def get_lov_repository() -> LOVRepository:
    global _repo
    if _repo is None:
        _repo = LOVRepository()
    return _repo
