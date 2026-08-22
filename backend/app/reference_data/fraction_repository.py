"""
Fraction to Decimal Reference Interface.
"""

class FractionRepository:
    def __init__(self):
        # TODO: Load Decimal_Fraction.xlsx
        pass

    def convert_fraction_to_decimal(self, fraction_str: str) -> str:
        raise NotImplementedError("Reference data unavailable (Decimal_Fraction.xlsx missing)")

_repo = None
def get_fraction_repository() -> FractionRepository:
    global _repo
    if _repo is None:
        _repo = FractionRepository()
    return _repo
