import re
import logging
from typing import Any, Optional, Dict, Tuple
from app.normalization.models import NormalizedAttributeResult

logger = logging.getLogger(__name__)


class NormalizationService:
    """
    Service responsible for converting raw technical specifications into canonical formats.
    Preserves original raw values and flags ambiguous inputs without guessing.
    """

    def __init__(self):
        self.alias_map = {
            "milw": "Milwaukee",
            "milw.": "Milwaukee",
            "wh": "White",
            "bk": "Black",
            "blk": "Black",
            "lt": "Light",
            "elect": "Electric",
            "dg": "Dark Gray",
            "sst": "Stainless Steel",
            "bss": "Black Stainless Steel",
            "in.": "in"
        }

    def normalize_attribute(self, attribute_name: str, raw_value: Any) -> NormalizedAttributeResult:
        """Dispatch attribute to its specialized normalizer based on name."""
        if raw_value is None:
            return NormalizedAttributeResult(
                raw_value=None,
                normalized_value=None,
                unit=None,
                is_ambiguous=False,
                requires_review=False
            )

        name_clean = attribute_name.lower().strip()

        if "voltage" in name_clean:
            return self.normalize_voltage(raw_value)
        elif "current" in name_clean:
            return self.normalize_current(raw_value)
        elif "frequency" in name_clean:
            return self.normalize_frequency(raw_value)
        elif "dimension" in name_clean or "size" in name_clean:
            return self.normalize_dimensions(raw_value)
        elif "pole" in name_clean:
            return self.normalize_poles(raw_value)
        elif "trip" in name_clean:
            return self.normalize_trip_class(raw_value)
        elif "power" in name_clean:
            return self.normalize_power(raw_value)
        elif "mounting" in name_clean:
            return self.normalize_mounting(raw_value)
        else:
            return self.normalize_generic(raw_value)

    # -------------------------------------------------------------------------
    # Voltage Normalizer
    # -------------------------------------------------------------------------
    def normalize_voltage(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        # Check for ambiguity expressions
        if self._is_ambiguous_text(s):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=None,
                is_ambiguous=True,
                requires_review=True,
                message=f"Ambiguous voltage value: '{s}'"
            )

        # Detect AC / DC
        current_type = None
        if re.search(r'vac|v\s*ac|\bac\b|\ba\.c\.', s, re.IGNORECASE):
            current_type = "AC"
        elif re.search(r'vdc|v\s*dc|\bdc\b|\bd\.c\.', s, re.IGNORECASE):
            current_type = "DC"

        # Match voltage range (e.g. "110 - 230 V", "400/690 V", "400 to 690 V", "12 - 24 V DC")
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:-|/|to)\s*(\d+(?:\.\d+)?)\s*(?:v|volts|vac|vdc)?(?:\s*(?:ac|dc))?', s, re.IGNORECASE)
        if range_match:
            low, high = range_match.group(1), range_match.group(2)
            suffix = f" {current_type}" if current_type else ""
            norm = f"{low}-{high} V{suffix}".strip()
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=norm,
                unit="V",
                metadata={"min_voltage": float(low), "max_voltage": float(high), "type": current_type}
            )

        # Match single numeric voltage (e.g. "400 volts", "400V", "400 V AC", "24 VDC", "0.4 kV")
        single_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:(k?v(?:olts?|ac|vdc)?)|(?:v\s*(?:ac|dc|a\.c\.|d\.c\.))|\bvolts?\b|\bkv\b)?', s, re.IGNORECASE)
        if single_match and single_match.group(1):
            num = float(single_match.group(1))
            if "kv" in s.lower():
                num = num * 1000.0  # Convert kV to V
            
            # Format number (omit trailing .0 for clean integers)
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            suffix = f" {current_type}" if current_type else ""
            norm = f"{num_str} V{suffix}".strip()

            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=norm,
                unit="V",
                numeric_value=num,
                metadata={"voltage_v": num, "type": current_type}
            )

        # Just a bare number
        if re.match(r'^\d+(?:\.\d+)?$', s):
            num = float(s)
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{num_str} V",
                unit="V",
                numeric_value=num
            )

        return NormalizedAttributeResult(
            raw_value=raw_value,
            normalized_value=None,
            is_ambiguous=True,
            requires_review=True,
            message=f"Could not parse voltage: '{s}'"
        )

    # -------------------------------------------------------------------------
    # Current Normalizer
    # -------------------------------------------------------------------------
    def normalize_current(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        if self._is_ambiguous_text(s):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=None,
                is_ambiguous=True,
                requires_review=True,
                message=f"Ambiguous current value: '{s}'"
            )

        # Match range (e.g. "0.28 to 0.4 A", "0.28 - 0.4 A", "0.28...0.4 A")
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:-|/|to|\.\.\.)\s*(\d+(?:\.\d+)?)\s*(?:a|amps?|amperes?|ma)?', s, re.IGNORECASE)
        if range_match:
            low, high = range_match.group(1), range_match.group(2)
            unit = "mA" if "ma" in s.lower() else "A"
            norm = f"{low}-{high} {unit}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=norm,
                unit=unit,
                metadata={"min_current": float(low), "max_current": float(high)}
            )

        # Match single numeric current (e.g. "10 amps", "10A", "16 amperes", "500 mA")
        single_match = re.search(r'(\d+(?:\.\d+)?)\s*(m?a(?:mps?|mperes?)?)\b', s, re.IGNORECASE)
        if single_match:
            num = float(single_match.group(1))
            unit_raw = single_match.group(2).lower()
            unit = "mA" if "ma" in unit_raw else "A"
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{num_str} {unit}",
                unit=unit,
                numeric_value=num if unit == "A" else num / 1000.0,
            )

        # Bare number
        if re.match(r'^\d+(?:\.\d+)?$', s):
            num = float(s)
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{num_str} A",
                unit="A",
                numeric_value=num
            )

        return NormalizedAttributeResult(
            raw_value=raw_value,
            normalized_value=None,
            is_ambiguous=True,
            requires_review=True,
            message=f"Could not parse current: '{s}'"
        )

    # -------------------------------------------------------------------------
    # Frequency Normalizer
    # -------------------------------------------------------------------------
    def normalize_frequency(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        if self._is_ambiguous_text(s):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=None,
                is_ambiguous=True,
                requires_review=True,
                message=f"Ambiguous frequency value: '{s}'"
            )

        # Dual frequency 50/60 Hz
        if re.search(r'50\s*(?:/|-|to|or|,)\s*60\s*(?:hz|hertz)?', s, re.IGNORECASE):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value="50/60 Hz",
                unit="Hz",
                metadata={"frequencies": [50.0, 60.0]}
            )

        # Single frequency (e.g. "50Hz", "60 Hertz", "400 Hz")
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hz|hertz)\b', s, re.IGNORECASE)
        if match:
            num = float(match.group(1))
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{num_str} Hz",
                unit="Hz",
                numeric_value=num
            )

        if s in ("50", "60", "400"):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{s} Hz",
                unit="Hz",
                numeric_value=float(s)
            )

        return NormalizedAttributeResult(
            raw_value=raw_value,
            normalized_value=None,
            is_ambiguous=True,
            requires_review=True,
            message=f"Could not parse frequency: '{s}'"
        )

    # -------------------------------------------------------------------------
    # Dimensions Normalizer
    # -------------------------------------------------------------------------
    def normalize_dimensions(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        if self._is_ambiguous_text(s):
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=None,
                is_ambiguous=True,
                requires_review=True,
                message=f"Ambiguous dimensions: '{s}'"
            )

        # Extract units if mentioned (mm, cm, in, inches)
        unit = "mm"
        scale = 1.0
        if re.search(r'cm|centimeter', s, re.IGNORECASE):
            unit = "mm"
            scale = 10.0
        elif re.search(r'inch|inches|\bin\b|\"', s, re.IGNORECASE):
            unit = "mm"
            scale = 25.4

        # Extract numeric components
        nums = re.findall(r'[-+]?\d+(?:\.\d+)?', s)
        clean_nums = [float(n) for n in nums if float(n) > 0]

        if len(clean_nums) == 3:
            h, w, d = [round(n * scale, 1) for n in clean_nums]
            h_str = f"{int(h)}" if h.is_integer() else f"{h}"
            w_str = f"{int(w)}" if w.is_integer() else f"{w}"
            d_str = f"{int(d)}" if d.is_integer() else f"{d}"
            norm = f"{h_str} x {w_str} x {d_str} mm"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=norm,
                unit="mm",
                metadata={"height_mm": h, "width_mm": w, "depth_mm": d}
            )
        elif len(clean_nums) == 2:
            h, w = [round(n * scale, 1) for n in clean_nums]
            h_str = f"{int(h)}" if h.is_integer() else f"{h}"
            w_str = f"{int(w)}" if w.is_integer() else f"{w}"
            norm = f"{h_str} x {w_str} mm"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=norm,
                unit="mm",
                metadata={"height_mm": h, "width_mm": w}
            )

        return NormalizedAttributeResult(
            raw_value=raw_value,
            normalized_value=s,
            unit=unit,
            is_ambiguous=True,
            requires_review=True,
            message="Unstandardized dimension format"
        )

    # -------------------------------------------------------------------------
    # Poles Normalizer
    # -------------------------------------------------------------------------
    def normalize_poles(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        if isinstance(raw_value, int):
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=raw_value, unit="poles", numeric_value=float(raw_value))

        match = re.search(r'(\d+)\s*(?:p|poles?|pole)?\b', s, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=num,
                unit="poles",
                numeric_value=float(num)
            )

        return NormalizedAttributeResult(raw_value=raw_value, normalized_value=s, is_ambiguous=True, requires_review=True)

    # -------------------------------------------------------------------------
    # Trip Class Normalizer
    # -------------------------------------------------------------------------
    def normalize_trip_class(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        match = re.search(r'(?:trip\s*class|class)?\s*(\d+[A-Za-z]?)\b', s, re.IGNORECASE)
        if match:
            cls_name = match.group(1).upper()
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"Class {cls_name}",
                unit=None,
                metadata={"class": cls_name}
            )

        return NormalizedAttributeResult(raw_value=raw_value, normalized_value=s)

    # -------------------------------------------------------------------------
    # Power Normalizer
    # -------------------------------------------------------------------------
    def normalize_power(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        # kW or HP
        match = re.search(r'(\d+(?:\.\d+)?)\s*(kw|kilowatts?|hp|horsepower)\b', s, re.IGNORECASE)
        if match:
            num = float(match.group(1))
            unit_raw = match.group(2).lower()
            unit = "HP" if "hp" in unit_raw or "horsepower" in unit_raw else "kW"
            num_str = f"{int(num)}" if num.is_integer() else f"{num}"
            return NormalizedAttributeResult(
                raw_value=raw_value,
                normalized_value=f"{num_str} {unit}",
                unit=unit,
                numeric_value=num
            )

        return NormalizedAttributeResult(raw_value=raw_value, normalized_value=s)

    # -------------------------------------------------------------------------
    # Mounting Normalizer
    # -------------------------------------------------------------------------
    def normalize_mounting(self, raw_value: Any) -> NormalizedAttributeResult:
        s = str(raw_value).strip()
        if not s:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=None)

        s_lower = s.lower()
        if "din" in s_lower and "rail" in s_lower:
            if "35" in s_lower:
                return NormalizedAttributeResult(raw_value=raw_value, normalized_value="DIN Rail (35mm)")
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value="DIN Rail")
        elif "panel" in s_lower:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value="Panel Mount")
        elif "screw" in s_lower:
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value="Screw Mounting")

        return NormalizedAttributeResult(raw_value=raw_value, normalized_value=s)

    # -------------------------------------------------------------------------
    # Generic Normalizer
    # -------------------------------------------------------------------------
    def resolve_aliases(self, raw: str) -> str:
        tokens = raw.split()
        resolved = []
        for t in tokens:
            t_lower = t.lower()
            if t_lower in self.alias_map:
                resolved.append(self.alias_map[t_lower])
            else:
                resolved.append(t)
        
        res = " ".join(resolved)
        # Handle inch quote notation like 1/2" -> 1/2 in
        res = re.sub(r'(\d(?:/\d+|\.\d+)?)\"', r'\1 in', res)
        return res

    def normalize_generic(self, raw_value: Any) -> NormalizedAttributeResult:
        if isinstance(raw_value, str):
            clean = raw_value.strip()
            clean = self.resolve_aliases(clean)
            return NormalizedAttributeResult(raw_value=raw_value, normalized_value=clean)
        return NormalizedAttributeResult(raw_value=raw_value, normalized_value=raw_value)

    def _is_ambiguous_text(self, s: str) -> bool:
        lower = s.lower()
        ambiguous_keywords = [
            "approx", "maybe", "varies", "depends", "custom",
            "unknown", "n/a", "tbd", "unspecified", "see manual",
            "either", "or other"
        ]
        return any(k in lower for k in ambiguous_keywords)


_default_normalizer: Optional[NormalizationService] = None


def get_normalization_service() -> NormalizationService:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = NormalizationService()
    return _default_normalizer
