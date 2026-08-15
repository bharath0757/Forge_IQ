import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.validation.models import ValidationResultItem, ValidationStatus, ValidationSeverity


class BaseValidationRule(ABC):
    """Abstract base class for a deterministic validation rule."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        """
        Execute rule on product attributes and return 0 or more ValidationResultItems.
        Never mutate attributes.
        """
        pass


class RequiredAttributeRule(BaseValidationRule):
    """Checks that essential attributes for a given category are present and non-null."""

    DEFAULT_REQUIRED = ["voltage", "current"]

    def __init__(self, required_attributes: Optional[List[str]] = None):
        self.required_attributes = required_attributes or self.DEFAULT_REQUIRED

    @property
    def name(self) -> str:
        return "RequiredAttributesCheck"

    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        results = []
        for req in self.required_attributes:
            attr_data = attributes.get(req)
            val = None
            evidence_ids = []

            if attr_data is not None:
                val = getattr(attr_data, "value", None) if hasattr(attr_data, "value") else attr_data.get("value")
                status = getattr(attr_data, "status", "") if hasattr(attr_data, "status") else attr_data.get("status", "")
                evidence_ids = getattr(attr_data, "evidence_ids", []) if hasattr(attr_data, "evidence_ids") else attr_data.get("evidence_ids", [])
                if str(status).upper() == "UNKNOWN":
                    val = None

            if val is None or val == "":
                results.append(
                    ValidationResultItem(
                        rule=self.name,
                        attribute_name=req,
                        passed=False,
                        status=ValidationStatus.FAILED,
                        severity=ValidationSeverity.HIGH,
                        message=f"Required attribute '{req}' is missing or marked UNKNOWN.",
                        evidence_ids=evidence_ids or [],
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        rule=self.name,
                        attribute_name=req,
                        passed=True,
                        status=ValidationStatus.PASSED,
                        severity=ValidationSeverity.LOW,
                        message=f"Required attribute '{req}' is present ({val}).",
                        evidence_ids=evidence_ids or [],
                    )
                )
        return results


class NumericFormatRule(BaseValidationRule):
    """Checks that numerical attributes parse cleanly into positive numbers."""

    NUMERIC_FIELDS = ["voltage", "current", "frequency", "poles", "power"]

    @property
    def name(self) -> str:
        return "NumericFormatCheck"

    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        results = []
        for field_name, attr_data in attributes.items():
            if not any(k in field_name.lower() for k in self.NUMERIC_FIELDS):
                continue

            val = getattr(attr_data, "value", None) if hasattr(attr_data, "value") else attr_data.get("value")
            evidence_ids = getattr(attr_data, "evidence_ids", []) if hasattr(attr_data, "evidence_ids") else attr_data.get("evidence_ids", [])
            if val is None:
                continue

            s = str(val).strip()
            # Extract numbers from string
            nums = re.findall(r'[-+]?\d+(?:\.\d+)?', s)
            if not nums:
                results.append(
                    ValidationResultItem(
                        rule=self.name,
                        attribute_name=field_name,
                        passed=False,
                        status=ValidationStatus.FAILED,
                        severity=ValidationSeverity.MEDIUM,
                        message=f"Attribute '{field_name}' value '{val}' contains no valid numeric value.",
                        evidence_ids=evidence_ids,
                    )
                )
            elif any(float(n) < 0 for n in nums):
                results.append(
                    ValidationResultItem(
                        rule=self.name,
                        attribute_name=field_name,
                        passed=False,
                        status=ValidationStatus.FAILED,
                        severity=ValidationSeverity.HIGH,
                        message=f"Attribute '{field_name}' value '{val}' contains negative numeric value.",
                        evidence_ids=evidence_ids,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        rule=self.name,
                        attribute_name=field_name,
                        passed=True,
                        status=ValidationStatus.PASSED,
                        severity=ValidationSeverity.LOW,
                        message=f"Numeric format for '{field_name}' is valid.",
                        evidence_ids=evidence_ids,
                    )
                )
        return results


class UnitConsistencyRule(BaseValidationRule):
    """Verifies that the unit assigned to an attribute matches its physical dimension."""

    ALLOWED_UNITS = {
        "voltage": {"v", "kv", "mv", "vac", "vdc", "volts", "v ac", "v dc"},
        "current": {"a", "ma", "ka", "amps", "amperes", "amp"},
        "frequency": {"hz", "khz", "mhz", "hertz"},
        "dimensions": {"mm", "cm", "in", "inch", "inches", "m"},
        "power": {"kw", "w", "mw", "hp", "horsepower"},
        "poles": {"poles", "pole", "p", ""},
    }

    @property
    def name(self) -> str:
        return "UnitConsistencyCheck"

    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        results = []
        for field_name, attr_data in attributes.items():
            unit = getattr(attr_data, "unit", None) if hasattr(attr_data, "unit") else attr_data.get("unit")
            val = getattr(attr_data, "value", None) if hasattr(attr_data, "value") else attr_data.get("value")
            evidence_ids = getattr(attr_data, "evidence_ids", []) if hasattr(attr_data, "evidence_ids") else attr_data.get("evidence_ids", [])

            if val is None:
                continue

            # Find matching expected unit group
            matching_key = None
            for k in self.ALLOWED_UNITS:
                if k in field_name.lower():
                    matching_key = k
                    break

            if matching_key:
                allowed = self.ALLOWED_UNITS[matching_key]
                # Check unit from field or inline unit in value
                unit_to_check = unit.lower().strip() if unit else None
                if not unit_to_check and isinstance(val, str):
                    # Try to extract trailing unit
                    m = re.search(r'[0-9]\s*([a-zA-Z]+(?:\s*[a-zA-Z]+)?)$', val.strip())
                    if m:
                        unit_to_check = m.group(1).lower().strip()

                if unit_to_check and unit_to_check not in allowed:
                    results.append(
                        ValidationResultItem(
                            rule=self.name,
                            attribute_name=field_name,
                            passed=False,
                            status=ValidationStatus.FAILED,
                            severity=ValidationSeverity.CRITICAL,
                            message=f"Unit mismatch for '{field_name}': '{unit_to_check}' is not a valid unit for {matching_key} (expected one of: {', '.join(sorted(allowed))}).",
                            evidence_ids=evidence_ids,
                            details={"unit": unit_to_check, "allowed_units": list(allowed)}
                        )
                    )
                else:
                    results.append(
                        ValidationResultItem(
                            rule=self.name,
                            attribute_name=field_name,
                            passed=True,
                            status=ValidationStatus.PASSED,
                            severity=ValidationSeverity.LOW,
                            message=f"Unit '{unit_to_check or 'default'}' is consistent for '{field_name}'.",
                            evidence_ids=evidence_ids,
                        )
                    )
        return results


class ImpossibleValueRule(BaseValidationRule):
    """Detects physically impossible or out-of-bounds technical values."""

    BOUNDS = {
        "voltage": (0.1, 100000.0, "V"),        # 0.1V to 100kV
        "current": (0.001, 10000.0, "A"),       # 1mA to 10kA
        "frequency": (10.0, 1000.0, "Hz"),      # 10Hz to 1kHz for power equipment
        "poles": (1, 12, "poles"),              # 1 to 12 poles
    }

    @property
    def name(self) -> str:
        return "ImpossibleValueCheck"

    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        results = []
        for field_name, attr_data in attributes.items():
            val = getattr(attr_data, "value", None) if hasattr(attr_data, "value") else attr_data.get("value")
            norm_val = getattr(attr_data, "normalized_value", None) if hasattr(attr_data, "normalized_value") else attr_data.get("normalized_value")
            evidence_ids = getattr(attr_data, "evidence_ids", []) if hasattr(attr_data, "evidence_ids") else attr_data.get("evidence_ids", [])

            if val is None:
                continue

            target_key = None
            for k in self.BOUNDS:
                if k in field_name.lower():
                    target_key = k
                    break

            if target_key:
                min_b, max_b, unit_label = self.BOUNDS[target_key]
                # Extract first numeric value
                nums = re.findall(r'[-+]?\d+(?:\.\d+)?', str(norm_val or val))
                if nums:
                    num = float(nums[0])
                    if num < min_b or num > max_b:
                        results.append(
                            ValidationResultItem(
                                rule=self.name,
                                attribute_name=field_name,
                                passed=False,
                                status=ValidationStatus.FAILED,
                                severity=ValidationSeverity.CRITICAL,
                                message=f"Impossible value detected: {num} {unit_label} is outside physical bounds ({min_b} - {max_b} {unit_label}) for '{field_name}'.",
                                evidence_ids=evidence_ids,
                                details={"value": num, "min": min_b, "max": max_b}
                            )
                        )
                    else:
                        results.append(
                            ValidationResultItem(
                                rule=self.name,
                                attribute_name=field_name,
                                passed=True,
                                status=ValidationStatus.PASSED,
                                severity=ValidationSeverity.LOW,
                                message=f"Value {num} {unit_label} is within physical bounds for '{field_name}'.",
                                evidence_ids=evidence_ids,
                            )
                        )
        return results


class DuplicateAttributeRule(BaseValidationRule):
    """Flags duplicate attribute definitions with divergent values."""

    @property
    def name(self) -> str:
        return "DuplicateAttributeCheck"

    def validate(
        self,
        attributes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResultItem]:
        # Checks if context has raw list of attributes with potential duplicates
        raw_list = context.get("raw_attributes_list") if context else None
        if not raw_list:
            return []

        counts: Dict[str, List[Any]] = {}
        for item in raw_list:
            name = getattr(item, "name", None) or item.get("name")
            val = getattr(item, "value", None) or item.get("value")
            if name:
                counts.setdefault(name, []).append(val)

        results = []
        for name, vals in counts.items():
            if len(vals) > 1:
                unique_vals = list(set(str(v) for v in vals))
                if len(unique_vals) > 1:
                    results.append(
                        ValidationResultItem(
                            rule=self.name,
                            attribute_name=name,
                            passed=False,
                            status=ValidationStatus.CONFLICT,
                            severity=ValidationSeverity.HIGH,
                            message=f"Duplicate attribute '{name}' found with conflicting values: {unique_vals}",
                            details={"conflicting_values": unique_vals}
                        )
                    )
        return results
