from fractions import Fraction
import re
from typing import Optional

class FractionNormalizer:
    """
    Converts decimals to standard fractional representations as per
    industrial conventions (e.g. 0.5 -> 1/2).
    Only converts if the decimal is exactly matching standard fractions
    (1/2, 1/4, 3/4, 1/8, 3/8, 5/8, 7/8, 1/16, etc. up to 1/32).
    """

    # Allowed denominators for industrial standard sizes
    ALLOWED_DENOMINATORS = {2, 4, 8, 16, 32}

    @classmethod
    def decimal_to_fraction_str(cls, num_str: str) -> str:
        try:
            val = float(num_str)
        except ValueError:
            return num_str
            
        whole = int(val)
        frac = val - whole
        
        if frac == 0:
            return str(whole)
            
        # Try to match with allowed denominators
        # 1/32 is 0.03125
        # we check if frac * denominator is very close to an integer
        for den in sorted(list(cls.ALLOWED_DENOMINATORS)):
            num = round(frac * den)
            if abs(frac - (num / den)) < 1e-6:
                if num == 0:
                    return str(whole)
                elif num == den:
                    return str(whole + 1)
                
                # reduce fraction
                f = Fraction(num, den)
                if whole > 0:
                    return f"{whole}-{f.numerator}/{f.denominator}"
                else:
                    return f"{f.numerator}/{f.denominator}"
                    
        # If it doesn't match standard fractions, leave it as decimal
        return num_str

    @classmethod
    def normalize_string(cls, text: str) -> str:
        """Finds decimals in text and replaces them with fractions where appropriate."""
        if not text:
            return text
            
        # find standalone decimals or decimals followed by standard units
        def repl(match):
            return cls.decimal_to_fraction_str(match.group(0))
            
        return re.sub(r'\b\d+\.\d+\b', repl, text)

