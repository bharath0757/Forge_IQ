"""
Generic product type detector from description text.
Returns candidate_type with confidence and status — does NOT map to official taxonomy.
"""
import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class ProductTypeStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNRESOLVED = "UNRESOLVED"


class ProductTypeResult(BaseModel):
    candidate_type: Optional[str] = None
    confidence: float = 0.0
    status: ProductTypeStatus = ProductTypeStatus.UNRESOLVED
    matched_pattern: Optional[str] = None


# Ordered from most specific to least specific
PRODUCT_TYPE_PATTERNS: List[tuple] = [
    # Abrasives
    (r"\bsanding\s+belt\b", "Sanding Belt", 0.95),
    (r"\b(?:metal\s+)?cut[\s-]?off\s+disc\b", "Cut-Off Disc", 0.93),
    (r"\bcut[\s-]?off\s+wheel\b", "Cut-Off Wheel", 0.93),
    (r"\bgrinding\s+wheel\b", "Grinding Wheel", 0.92),
    (r"\bdual\s+metal\s+cut\s+(?:and|n)\s+grind\s+disc\b", "Cut & Grind Disc", 0.92),
    (r"\bstikit\s+film\b", "Stikit Film Disc", 0.92),
    (r"\babranet\b", "Abranet Abrasive Sheet", 0.90),
    (r"\bhiolit\b", "Hiolit Abrasive Disc", 0.90),
    (r"\bsanding\s+sponge\b", "Sanding Sponge", 0.90),
    (r"\b(?:abrasive\s+|sanding\s+)?flap\s+disc\b", "Flap Disc", 0.90),
    (r"\b(?:abrasive\s+|sanding\s+)?disc\b", "Abrasive Disc", 0.85),
    
    # Saws & Tools
    (r"\b(?:laminate\s+track\s+)?saw\s+blade\b", "Saw Blade", 0.95),
    (r"\btrack\s+saw\b", "Track Saw", 0.92),
    (r"\bimpact\s+(?:driver\s+drill|driver)\b", "Impact Driver", 0.93),
    (r"\bimpact\s+wrench\b", "Impact Wrench", 0.93),
    (r"\bgrease\s+gun\b", "Grease Gun", 0.93),
    (r"\b(?:cordless\s+)?drill\b", "Cordless Drill", 0.88),
    (r"\b(?:laser\s+green|cross\s+line\s+laser|laser)\b", "Laser Level", 0.90),
    (r"\b(?:drive\s+bit|router\s+bit|drill\s+bit|bit\s+holder)\b", "Driver Bit", 0.88),
    (r"\b(?:heated\s+)?glove\b", "Work Gloves", 0.88),
    (r"\b(?:safety\s+glasses|eyewear)\b", "Safety Glasses", 0.88),
    
    # Decking & Building
    (r"\b(?:pvc\s+|composite\s+)?decking\b", "Decking Board", 0.92),
    (r"\b(?:composite\s+)?deck\s+board\b", "Deck Board", 0.92),
    (r"\b(?:pvc\s+)?fascia\b", "Fascia Board", 0.92),
    (r"\bpost\s+trim\b", "Post Trim", 0.90),
    (r"\bpost\s+sleeve\b", "Post Sleeve", 0.90),
    (r"\brail\s+kit\b", "Railing Kit", 0.90),
    (r"\brail\s+panel\b", "Railing Panel", 0.90),
    (r"\b(?:patio\s+dr|gliding\s+patio)\b", "Patio Door", 0.92),
    (r"\b(?:bsmt\s+)?hopper\s+(?:dla|window)?\b", "Hopper Window", 0.90),
    (r"\bskylight|skylt\b", "Skylight", 0.92),
    (r"\b(?:hardieplank|lap\s+siding|siding\s+smooth)\b", "Lap Siding", 0.92),
    (r"\bhardiepanel\b", "Siding Panel", 0.92),
    (r"\b(?:drywall|gypsum|sheetrock)\b", "Drywall Panel", 0.90),
    (r"\b(?:plusosb|sub\s+floor|subfloor|osb)\b", "OSB Subfloor", 0.90),
    (r"\bmortar\b", "Mortar Mix", 0.90),
    (r"\b(?:ice\s+guard|eaveguard|weather\s+lock)\b", "Roofing Ice Guard", 0.90),
    
    # Appliances
    (r"\bdishwasher\b", "Dishwasher", 0.95),
    (r"\b(?:elect\s+|gas\s+)?dryer\b", "Dryer", 0.95),
    (r"\b(?:elect\s+)?washer\b", "Washing Machine", 0.95),
    (r"\blaundry\s+center\b", "Laundry Center", 0.95),
    (r"\b(?:french\s+door\s+)?(?:refrigerator|fridge)\b", "Refrigerator", 0.95),
    (r"\b(?:range|oven|cooktop)\b", "Range / Oven", 0.93),
    (r"\bespresso\s+machine\b", "Espresso Machine", 0.93),
    (r"\bheater\s+kit\b", "Heater Kit", 0.90),
    
    # Lighting & Electrical
    (r"\bchandelier\b", "Chandelier", 0.95),
    (r"\bpendant\s+(?:lt|light)\b", "Pendant Light", 0.93),
    (r"\bwall\s+(?:light|lt|sconce)\b", "Wall Light", 0.93),
    (r"\bbath\s+light\b", "Bath Vanity Light", 0.93),
    (r"\b(?:wrap\s+light|ceiling\s+lt|highbay|flush\s+mount)\b", "Ceiling Light Fixture", 0.90),
    (r"\b(?:led\s+st\d+|led\s+par\d+|led\s+med|led\s+multi|led\s+a\d+|led\s+br\d+|\d+w\s+led|light\s+bulb)\b", "LED Light Bulb", 0.92),
    (r"\b(?:ceiling\s+)?fan\b", "Ceiling Fan", 0.90),
    (r"\bdimmer\b", "Dimmer Switch", 0.92),
    (r"\b(?:box\s+cover|decor\s+plate|wall\s+plate)\b", "Wall Plate Cover", 0.90),
    (r"\b(?:oct\s+box|square\s+box|2g\s+box)\b", "Electrical Junction Box", 0.90),
    (r"\b(?:elect\s+tape|vinyl\s+tape)\b", "Electrical Tape", 0.90),
    (r"\b(?:outlet|receptacle|gfci)\b", "Receptacle Outlet", 0.90),
    (r"\b(?:circuit\s+breaker|motor\s+protector)\b", "Circuit Breaker", 0.92),
    (r"\bcontactor\b", "Contactor", 0.92),
    (r"\bproximity\s+sensor\b", "Proximity Sensor", 0.92),
    (r"\bswitch\b", "Switch", 0.82),
    (r"\blumber\b", "Lumber", 0.80),
]


class ProductTypeDetector:
    """Detect candidate product types from free-text descriptions."""

    def detect(self, description: str, part_number: str = "") -> ProductTypeResult:
        text = f"{part_number} {description}".strip()
        if not text:
            return ProductTypeResult()

        lower = text.lower()
        best: Optional[ProductTypeResult] = None

        for pattern, type_name, confidence in PRODUCT_TYPE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                status = (
                    ProductTypeStatus.CANDIDATE
                    if confidence >= 0.85
                    else ProductTypeStatus.LOW_CONFIDENCE
                )
                result = ProductTypeResult(
                    candidate_type=type_name,
                    confidence=confidence,
                    status=status,
                    matched_pattern=pattern,
                )
                if best is None or confidence > best.confidence:
                    best = result

        return best or ProductTypeResult()


_default_detector: Optional[ProductTypeDetector] = None


def get_product_type_detector() -> ProductTypeDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = ProductTypeDetector()
    return _default_detector
