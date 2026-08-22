"""
ForgeIQ Entity Resolution Service
Resolves brand/manufacturer strings against a canonical master list.
Returns structured results with confidence and match type.
"""
import re
from enum import Enum
from typing import Optional, Dict, List, Tuple
from pydantic import BaseModel

from app.reference_data.entity_masters import MANUFACTURER_ALIASES, BRAND_ALIASES


class MatchType(str, Enum):
    EXACT = "EXACT"
    NORMALIZED = "NORMALIZED"
    FUZZY = "FUZZY"
    UNRESOLVED = "UNRESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EntityResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNRESOLVED = "UNRESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EntityResolutionResult(BaseModel):
    """Structured result from entity resolution."""
    raw_value: Optional[str] = None
    raw_name: Optional[str] = None
    raw_code: Optional[str] = None
    normalized_value: Optional[str] = None
    canonical_value: Optional[str] = None
    confidence: float = 0.0
    match_type: MatchType = MatchType.UNRESOLVED
    status: EntityResolutionStatus = EntityResolutionStatus.UNRESOLVED


# Known placeholders that should resolve to None
BAD_PLACEHOLDERS = {
    "-- unbranded --",
    "-- no unilog brand --",
    "-- no dib brand --",
    "-- no brand --",
    "-- no manufacturer --",
    "n/a",
    "na",
    "none",
    "unknown",
    "tbd",
    "not specified",
    "unspecified",
    "not available",
    "null",
    "-",
    "--",
    ".",
}

# Common brand normalizations (lowercase → canonical)
CANONICAL_BRANDS: Dict[str, str] = {
    "siemens": "Siemens",
    "siemens ag": "Siemens",
    "siemens ltd": "Siemens",
    "siemens ltd.": "Siemens",
    "abb": "ABB",
    "abb ltd": "ABB",
    "abb inc": "ABB",
    "schneider": "Schneider Electric",
    "schneider electric": "Schneider Electric",
    "schneider-electric": "Schneider Electric",
    "se": "Schneider Electric",
    "eaton": "Eaton",
    "eaton corporation": "Eaton",
    "eaton corp": "Eaton",
    "phoenix contact": "Phoenix Contact",
    "phoenixcontact": "Phoenix Contact",
    "phoenix": "Phoenix Contact",
    "honeywell": "Honeywell",
    "ge": "GE",
    "general electric": "GE",
    "rockwell": "Rockwell Automation",
    "rockwell automation": "Rockwell Automation",
    "allen-bradley": "Rockwell Automation",
    "allen bradley": "Rockwell Automation",
    "omron": "Omron",
    "mitsubishi": "Mitsubishi Electric",
    "mitsubishi electric": "Mitsubishi Electric",
    "danfoss": "Danfoss",
    "emerson": "Emerson",
    "parker": "Parker Hannifin",
    "parker hannifin": "Parker Hannifin",
    "bosch": "Bosch",
    "bosch rexroth": "Bosch Rexroth",
    "festo": "Festo",
    "weidmuller": "Weidmüller",
    "weidmüller": "Weidmüller",
    "wago": "WAGO",
    "legrand": "Legrand",
    "hager": "Hager",
    "diablo": "Diablo",
    "3m": "3M",
    "milwaukee": "Milwaukee",
    "milw": "Milwaukee",
    "freud": "Freud",
    "mirka": "Mirka",
    "kichler": "Kichler",
    "trex": "Trex",
    "timbertech": "TimberTech",
    "azek": "Azek",
    "dewalt": "DeWalt",
    "makita": "Makita",
    "festool": "Festool",
    "leviton": "Leviton",
    "philips": "Philips",
    "whirlpool": "Whirlpool",
    "kitchenaid": "KitchenAid",
    "kitchen aid": "KitchenAid",
    "lg": "LG",
}


class EntityResolutionService:
    """
    Resolves brand/manufacturer strings against a canonical master list.
    Returns structured EntityResolutionResult with confidence and match type.
    """

    def __init__(
        self,
        custom_brands: Optional[Dict[str, str]] = None,
        custom_manufacturers: Optional[Dict[str, Tuple[str, str]]] = None,
    ):
        self.master_brands: Dict[str, str] = dict(CANONICAL_BRANDS)
        self.master_brands.update(BRAND_ALIASES)
        if custom_brands:
            self.master_brands.update(custom_brands)

        self.master_manufacturers: Dict[str, Tuple[str, str]] = dict(MANUFACTURER_ALIASES)
        if custom_manufacturers:
            self.master_manufacturers.update(custom_manufacturers)

    def resolve_brand(self, raw_brand: Optional[str]) -> EntityResolutionResult:
        """Resolve a brand string to a canonical brand with confidence."""
        return self._resolve_entity(raw_brand, entity_type="brand")

    def resolve_manufacturer(self, raw_manufacturer: Optional[str]) -> EntityResolutionResult:
        """Resolve a manufacturer string to a canonical manufacturer with confidence."""
        return self._resolve_entity(raw_manufacturer, entity_type="manufacturer", use_manufacturer_master=True)

    def clean_brand(self, raw_brand: str) -> Optional[str]:
        """
        Convenience method for backward compatibility.
        Returns just the cleaned canonical brand string.
        """
        result = self.resolve_brand(raw_brand)
        return result.canonical_value

    def clean_manufacturer(self, raw_mfg: str) -> Optional[str]:
        """
        Convenience method for backward compatibility.
        Returns just the cleaned canonical manufacturer string.
        """
        result = self.resolve_manufacturer(raw_mfg)
        return result.canonical_value

    def _resolve_entity(
        self,
        raw_value: Optional[str],
        entity_type: str = "brand",
        use_manufacturer_master: bool = False,
    ) -> EntityResolutionResult:
        """Core resolution logic for brand/manufacturer entities."""
        if raw_value is None or not raw_value.strip():
            return EntityResolutionResult(
                raw_value=raw_value,
                raw_name=None,
                raw_code=None,
                normalized_value=None,
                canonical_value=None,
                confidence=0.0,
                match_type=MatchType.UNRESOLVED,
                status=EntityResolutionStatus.UNRESOLVED,
            )

        stripped = raw_value.strip()
        raw_name = stripped
        raw_code = None
        match = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", stripped)
        if match:
            raw_name = match.group(1).strip()
            raw_code = match.group(2).strip()

        if raw_name.lower() in BAD_PLACEHOLDERS or stripped.lower() in BAD_PLACEHOLDERS:
            return EntityResolutionResult(
                raw_value=raw_value,
                raw_name=raw_name,
                raw_code=raw_code,
                normalized_value=None,
                canonical_value=None,
                confidence=0.0,
                match_type=MatchType.UNRESOLVED,
                status=EntityResolutionStatus.UNRESOLVED,
            )

        normalized = re.sub(r"\s+", " ", raw_name.lower()).strip()
        normalized = re.sub(r"[.,;:]+$", "", normalized).strip()
        cleaned_for_match = self._strip_suffixes(normalized)

        if use_manufacturer_master:
            for key in (normalized, cleaned_for_match):
                if key in self.master_manufacturers:
                    canonical, code = self.master_manufacturers[key]
                    return EntityResolutionResult(
                        raw_value=raw_value,
                        raw_name=raw_name,
                        raw_code=raw_code or code,
                        normalized_value=normalized,
                        canonical_value=canonical,
                        confidence=0.95,
                        match_type=MatchType.NORMALIZED,
                        status=EntityResolutionStatus.RESOLVED,
                    )
            if raw_code:
                code_lower = raw_code.lower()
                for _key, (canonical, code) in self.master_manufacturers.items():
                    if code and code.lower() == code_lower:
                        return EntityResolutionResult(
                            raw_value=raw_value,
                            raw_name=raw_name,
                            raw_code=raw_code,
                            normalized_value=normalized,
                            canonical_value=canonical,
                            confidence=0.90,
                            match_type=MatchType.NORMALIZED,
                            status=EntityResolutionStatus.RESOLVED,
                        )
            for key, (canonical, code) in self.master_manufacturers.items():
                if len(normalized) >= 4 and (key.startswith(normalized) or normalized.startswith(key)):
                    return EntityResolutionResult(
                        raw_value=raw_value,
                        raw_name=raw_name,
                        raw_code=raw_code or code,
                        normalized_value=normalized,
                        canonical_value=canonical,
                        confidence=0.78,
                        match_type=MatchType.FUZZY,
                        status=EntityResolutionStatus.LOW_CONFIDENCE,
                    )
            title_cased = raw_name.title() if raw_name.isupper() or raw_name.islower() else raw_name
            return EntityResolutionResult(
                raw_value=raw_value,
                raw_name=raw_name,
                raw_code=raw_code,
                normalized_value=normalized,
                canonical_value=title_cased,
                confidence=0.40,
                match_type=MatchType.UNRESOLVED,
                status=EntityResolutionStatus.UNRESOLVED,
            )

        if normalized in self.master_brands:
            canonical = self.master_brands[normalized]
            match_type = MatchType.EXACT if raw_name == canonical else MatchType.NORMALIZED
            return EntityResolutionResult(
                raw_value=raw_value,
                raw_name=raw_name,
                raw_code=raw_code,
                normalized_value=normalized,
                canonical_value=canonical,
                confidence=0.98 if match_type == MatchType.EXACT else 0.95,
                match_type=match_type,
                status=EntityResolutionStatus.RESOLVED,
            )

        if cleaned_for_match in self.master_brands:
            canonical = self.master_brands[cleaned_for_match]
            return EntityResolutionResult(
                raw_value=raw_value,
                raw_name=raw_name,
                raw_code=raw_code,
                normalized_value=normalized,
                canonical_value=canonical,
                confidence=0.90,
                match_type=MatchType.NORMALIZED,
                status=EntityResolutionStatus.RESOLVED,
            )

        for known_key, canonical in self.master_brands.items():
            if known_key.startswith(normalized) and len(normalized) >= 3:
                return EntityResolutionResult(
                    raw_value=raw_value,
                    raw_name=raw_name,
                    raw_code=raw_code,
                    normalized_value=normalized,
                    canonical_value=canonical,
                    confidence=0.75,
                    match_type=MatchType.FUZZY,
                    status=EntityResolutionStatus.LOW_CONFIDENCE,
                )

        title_cased = raw_name.title() if raw_name.isupper() or raw_name.islower() else raw_name
        return EntityResolutionResult(
            raw_value=raw_value,
            raw_name=raw_name,
            raw_code=raw_code,
            normalized_value=normalized,
            canonical_value=title_cased,
            confidence=0.40,
            match_type=MatchType.UNRESOLVED,
            status=EntityResolutionStatus.UNRESOLVED,
        )

    @staticmethod
    def _strip_suffixes(value: str) -> str:
        """Remove common company suffixes for matching."""
        suffixes = [
            " inc", " inc.", " corp", " corp.", " corporation",
            " ltd", " ltd.", " limited", " llc", " llc.",
            " gmbh", " ag", " sa", " plc", " co", " co.",
            " group", " industries", " international",
        ]
        result = value
        for suffix in suffixes:
            if result.endswith(suffix):
                result = result[: -len(suffix)].strip()
        return result


_default_entity_resolver: Optional[EntityResolutionService] = None


def get_entity_resolution_service() -> EntityResolutionService:
    global _default_entity_resolver
    if _default_entity_resolver is None:
        _default_entity_resolver = EntityResolutionService()
    return _default_entity_resolver
