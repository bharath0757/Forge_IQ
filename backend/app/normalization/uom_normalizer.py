import re

class UOMNormalizer:
    """
    Standardizes units of measure formats using engineering heuristics (HEURISTIC).
    Rule: VALUE + SPACE + STANDARD UNIT (e.g. 24in -> 24 in)
    Note: Official UniHack/Unilog Master UOM Standards table is UNAVAILABLE.
    """
    
    STANDARD_UNITS = {
        # Length
        "in": "in", "in.": "in", "inch": "in", "inches": "in", '\"': "in",
        "ft": "ft", "ft.": "ft", "foot": "ft", "feet": "ft", "\'": "ft",
        "mm": "mm", "cm": "cm", "m": "m", "meter": "m", "meters": "m",
        
        # Weight
        "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
        "oz": "oz", "ounce": "oz", "ounces": "oz",
        "g": "g", "kg": "kg",
        
        # Electricity
        "v": "V", "volts": "V", "volt": "V", "vac": "VAC", "vdc": "VDC", "kv": "kV",
        "a": "A", "amp": "A", "amps": "A", "amperes": "A", "ma": "mA",
        "w": "W", "watts": "W", "kw": "kW",
        "hz": "Hz", "hertz": "Hz",
        
        # Other
        "psi": "psi", "bar": "bar", "deg": "deg", "c": "C", "f": "F"
    }

    @classmethod
    def normalize_value_and_unit(cls, raw: str) -> str:
        if not raw:
            return raw
            
        # Pattern to match numbers (including fractions like 1-1/4) followed optionally by space, then unit letters/symbols
        pattern = r'^([\d\.\-\/]+)\s*([a-zA-Z\.\'\"\°]+)?$'
        match = re.match(pattern, str(raw).strip())
        
        if match:
            value_part = match.group(1)
            unit_part = match.group(2)
            
            if unit_part:
                unit_lower = unit_part.lower()
                # Check for standard mapping
                mapped_unit = cls.STANDARD_UNITS.get(unit_lower, unit_part)
                # Ensure exactly one space
                return f"{value_part} {mapped_unit}".strip()
            
        return str(raw).strip()

