"""
ForgeIQ Taxonomy Engine
Classifies products into Dept, Class, Fine, and Classpath.
Returns structured results with confidence and status.
"""
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel


class TaxonomyStatus(str, Enum):
    RESOLVED = "RESOLVED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNRESOLVED = "UNRESOLVED"
    HEURISTIC = "HEURISTIC"


class TaxonomyResult(BaseModel):
    """Structured result from taxonomy classification."""
    dept: str = "Unclassified"
    class_name: str = "Unclassified"
    fine: str = "Unclassified"
    classpath: str = "Unclassified"
    confidence: float = 0.0
    status: TaxonomyStatus = TaxonomyStatus.UNRESOLVED


# Keyword-based classification rules
# Each rule: (keywords_in_category, keywords_in_description) → taxonomy
TAXONOMY_RULES: List[Dict] = [
    # Abrasives
    {
        "keywords": ["sanding belt", "abrasive belt"],
        "desc_keywords": ["sanding belt", "abrasive belt", "sandpaper"],
        "dept": "Tools",
        "class_name": "Abrasives",
        "fine": "Sanding Belts",
    },
    {
        "keywords": ["cut-off disc", "cutting wheel", "grinding wheel"],
        "desc_keywords": ["cut-off disc", "cut off disc", "cut and grind disc", "cut n grind", "cutting wheel", "grinding wheel", "cut-off wheel"],
        "dept": "Tools",
        "class_name": "Abrasives",
        "fine": "Cut-Off Discs",
    },
    {
        "keywords": ["abrasive", "stikit", "hiolit", "abranet"],
        "desc_keywords": ["stikit", "hiolit", "abranet", "cubitron", "abrasive disc", "sanding disc", "sanding sponge", "sanding sheet", "disc/box", "flap disc"],
        "dept": "Tools",
        "class_name": "Abrasives",
        "fine": "Abrasive Discs",
    },
    # Saws, Blades & Power Tools
    {
        "keywords": ["saw blade", "circular blade"],
        "desc_keywords": ["saw blade", "track saw blade", "circular blade", "laminate track saw", "blade"],
        "dept": "Tools",
        "class_name": "Saw Blades & Accessories",
        "fine": "Saw Blades",
    },
    {
        "keywords": ["power tool", "drill", "impact driver", "impact wrench"],
        "desc_keywords": ["impact driver", "driver drill", "impact wrench", "grease gun", "cordless drill", "power tool", "rotary tool", "grinder", "sander"],
        "dept": "Tools",
        "class_name": "Power Tools",
        "fine": "Drills & Drivers",
    },
    {
        "keywords": ["tool kit", "starter kit", "combo kit"],
        "desc_keywords": ["starter kit", "combo kit", "tool kit"],
        "dept": "Tools",
        "class_name": "Power Tools",
        "fine": "Tool Kits",
    },
    {
        "keywords": ["drive bit", "router bit", "drill bit"],
        "desc_keywords": ["drive bit", "router bit", "drill bit", "bit holder", "carrying bit", "insert bit", "driver bit"],
        "dept": "Tools",
        "class_name": "Tool Accessories",
        "fine": "Bits & Drivers",
    },
    {
        "keywords": ["laser", "level", "measuring tape"],
        "desc_keywords": ["laser green", "cross line", "self-level", "measuring tape", "tape measure", "inflator gauge", "pressure gauge", "level"],
        "dept": "Tools",
        "class_name": "Measuring & Layout",
        "fine": "Measuring Tools",
    },
    {
        "keywords": ["safety", "ppe", "glove", "eyewear"],
        "desc_keywords": ["heated glove", "eyewear", "safety glasses", "firewatch", "first alert", "smoke alarm", "hearing protection"],
        "dept": "Safety & Security",
        "class_name": "Safety Equipment",
        "fine": "Safety & PPE",
    },
    {
        "keywords": ["hand tool", "trowel", "fence"],
        "desc_keywords": ["trowel", "kneeling pad", "featherboard", "xtender fence", "clamp", "vise", "pliers", "wrench", "cutter"],
        "dept": "Tools",
        "class_name": "Hand Tools & Accessories",
        "fine": "General Tools",
    },
    # Roofing, Insulation & Masonry
    {
        "keywords": ["roofing", "underlayment", "shingle"],
        "desc_keywords": ["rainscreen", "ice guard", "eaveguard", "weather lock", "weathr lk", "trudef", "shingle", "roofing", "premier rib"],
        "dept": "Building Materials",
        "class_name": "Roofing & Gutters",
        "fine": "Roofing & Underlayment",
    },
    {
        "keywords": ["insulation", "sheathing", "drywall"],
        "desc_keywords": ["r-sheathing", "insulated sheathing", "drywall", "gypsum", "sheetrock", "firelite", "easi-lite", "fine fissured", "ceiling tile"],
        "dept": "Building Materials",
        "class_name": "Drywall & Ceilings",
        "fine": "Drywall & Ceiling Panels",
    },
    {
        "keywords": ["mortar", "stone", "masonry"],
        "desc_keywords": ["mortar", "type n", "cast stone", "cement", "joint systems", "emseal"],
        "dept": "Building Materials",
        "class_name": "Masonry & Concrete",
        "fine": "Mortar & Stone",
    },
    # Decking, Siding & Lumber
    {
        "keywords": ["decking", "deck"],
        "desc_keywords": ["decking", "deck board", "composite decking", "pvc decking", "grooved", "sq edge", "transcend", "lineage", "enhance", "vintage azek", "harvest azek", "reserve azek", "landmark azek"],
        "dept": "Building Materials",
        "class_name": "Lumber & Composites",
        "fine": "Decking",
    },
    {
        "keywords": ["fascia"],
        "desc_keywords": ["fascia", "pvc fascia", "composite fascia"],
        "dept": "Building Materials",
        "class_name": "Lumber & Composites",
        "fine": "Fascia",
    },
    {
        "keywords": ["post trim", "railing", "baluster"],
        "desc_keywords": ["post trim", "post cap", "post sleeve", "rail kit", "rail panel", "baluster", "gate", "finyline", "heritage post", "support post", "blank post", "ada wall mount", "ada rail"],
        "dept": "Building Materials",
        "class_name": "Deck & Railing",
        "fine": "Railing & Accessories",
    },
    {
        "keywords": ["siding", "lap siding"],
        "desc_keywords": ["hardieplank", "hardiepanel", "hardie", "smartside", "lap siding", "siding smooth", "trim board"],
        "dept": "Building Materials",
        "class_name": "Siding",
        "fine": "Lap Siding",
    },
    {
        "keywords": ["engineered wood", "osb"],
        "desc_keywords": ["osb", "sub floor", "subfloor", "plusosb", "underlayment"],
        "dept": "Building Materials",
        "class_name": "Engineered Wood",
        "fine": "Subfloor & OSB",
    },
    {
        "keywords": ["lumber", "deck board"],
        "desc_keywords": ["lumber", "timber", "pressure treated", "pvc board", "beam", "stud"],
        "dept": "Building Materials",
        "class_name": "Lumber & Composites",
        "fine": "Lumber",
    },
    {
        "keywords": ["window", "door", "skylight"],
        "desc_keywords": ["patio dr", "patio door", "gliding patio", "window", "door", "skylt", "skylight", "hopper", "ecoliteplus", "bsmt ecolite"],
        "dept": "Building Materials",
        "class_name": "Doors & Windows",
        "fine": "Doors & Windows",
    },
    # Appliances
    {
        "keywords": ["dishwasher"],
        "desc_keywords": ["dishwasher", "dish washer"],
        "dept": "Appliances",
        "class_name": "Kitchen Appliances",
        "fine": "Dishwashers",
    },
    {
        "keywords": ["dryer"],
        "desc_keywords": ["dryer", "sq elect dryer", "sq gas dryer", "electric dryer", "gas dryer"],
        "dept": "Appliances",
        "class_name": "Laundry Appliances",
        "fine": "Dryers",
    },
    {
        "keywords": ["washer", "laundry"],
        "desc_keywords": ["washer", "sq washer", "sq elect washer", "washing machine", "laundry center"],
        "dept": "Appliances",
        "class_name": "Laundry Appliances",
        "fine": "Washers",
    },
    {
        "keywords": ["refrigerator", "fridge"],
        "desc_keywords": ["refrigerator", "fridge", "french door fridge"],
        "dept": "Appliances",
        "class_name": "Kitchen Appliances",
        "fine": "Refrigerators",
    },
    {
        "keywords": ["range", "oven", "cooktop"],
        "desc_keywords": ["range", "oven", "cooktop", "stove"],
        "dept": "Appliances",
        "class_name": "Kitchen Appliances",
        "fine": "Ranges & Ovens",
    },
    {
        "keywords": ["espresso", "coffee"],
        "desc_keywords": ["espresso", "coffee maker", "espresso machine"],
        "dept": "Appliances",
        "class_name": "Small Appliances",
        "fine": "Coffee & Espresso Makers",
    },
    {
        "keywords": ["heater kit", "appliance part"],
        "desc_keywords": ["heater kit", "appliance part", "replacement kit"],
        "dept": "Appliances",
        "class_name": "Appliance Parts",
        "fine": "Replacement Parts",
    },
    # Lighting
    {
        "keywords": ["chandelier"],
        "desc_keywords": ["chandelier", "chand lt"],
        "dept": "Electrical",
        "class_name": "Lighting",
        "fine": "Chandeliers",
    },
    {
        "keywords": ["pendant"],
        "desc_keywords": ["pendant", "pendant lt", "pendant light"],
        "dept": "Electrical",
        "class_name": "Lighting",
        "fine": "Pendant Lights",
    },
    {
        "keywords": ["wall light", "sconce"],
        "desc_keywords": ["wall light", "wall lt", "wall sconce", "sconce", "bath light", "vanity light"],
        "dept": "Electrical",
        "class_name": "Lighting",
        "fine": "Wall Lights",
    },
    {
        "keywords": ["ceiling light", "luminaire", "fixture"],
        "desc_keywords": ["wrap light", "flush mount", "ceiling lt", "highbay", "high bay light", "nuvo highbay", "luminaire", "fixture", "strip light", "troffer", "streamlight", "flashlight", "led lt"],
        "dept": "Electrical",
        "class_name": "Lighting",
        "fine": "Ceiling & Fixture Lights",
    },
    {
        "keywords": ["light bulb", "led bulb", "lamp"],
        "desc_keywords": ["led st", "led par", "led med", "led multi", "led a19", "led br", "led g25", "led b11", "led cct", "lamp", "light bulb", "flood light", "led flood"],
        "dept": "Electrical",
        "class_name": "Lighting",
        "fine": "Light Bulbs",
    },
    {
        "keywords": ["ceiling fan", "fan"],
        "desc_keywords": ["ceiling fan", "fan motor", "hunter fan"],
        "dept": "Electrical",
        "class_name": "Fans",
        "fine": "Ceiling Fans",
    },
    # Hardware & Fasteners
    {
        "keywords": ["hinge"],
        "desc_keywords": ["hinge", "door hinge", "butt hinge", "hager hinge"],
        "dept": "Hardware",
        "class_name": "Door & Cabinet Hardware",
        "fine": "Hinges",
    },
    {
        "keywords": ["nail", "screw", "fastener"],
        "desc_keywords": ["nail", "screw", "staple", "fastener", "anchor", "bolt", "bracket"],
        "dept": "Hardware",
        "class_name": "Fasteners",
        "fine": "Nails & Screws",
    },
    # Electrical Wiring & Controls & Power
    {
        "keywords": ["dimmer"],
        "desc_keywords": ["dimmer", "dimming switch", "lighting control"],
        "dept": "Electrical",
        "class_name": "Lighting Controls",
        "fine": "Dimmers",
    },
    {
        "keywords": ["box cover", "wall plate"],
        "desc_keywords": ["box cover", "decor plate", "wall plate", "cover plate", "plate"],
        "dept": "Electrical",
        "class_name": "Boxes & Covers",
        "fine": "Wall Plates & Covers",
    },
    {
        "keywords": ["electrical box", "oct box", "square box"],
        "desc_keywords": ["oct box", "square box", "2g box", "box w/bracket", "box w/hanger", "junction box"],
        "dept": "Electrical",
        "class_name": "Boxes & Covers",
        "fine": "Electrical Boxes",
    },
    {
        "keywords": ["wire", "cable", "cord"],
        "desc_keywords": ["cord grip", "conduit", "wire", "cable", "cord", "elect tape", "vinyl elect tape", "vinyl tape", "tape", "hanger"],
        "dept": "Electrical",
        "class_name": "Wire & Cable",
        "fine": "Wire & Cable Accessories",
    },
    {
        "keywords": ["battery", "power supply"],
        "desc_keywords": ["battery", "jumpstart", "pwr supply", "power supply", "battery mount", "psu", "dc power", "ac/dc"],
        "dept": "Electrical",
        "class_name": "Power Supplies & Batteries",
        "fine": "Batteries & Power Supplies",
    },
    {
        "keywords": ["outlet", "receptacle"],
        "desc_keywords": ["outlet", "receptacle", "gfci", "tamper resistant"],
        "dept": "Electrical",
        "class_name": "Wiring Devices",
        "fine": "Outlets",
    },
    {
        "keywords": ["switch", "disconnect"],
        "desc_keywords": ["switch", "disconnect switch", "safety switch"],
        "dept": "Electrical",
        "class_name": "Switches",
        "fine": "General Switches",
    },
    {
        "keywords": ["circuit breaker", "breaker"],
        "desc_keywords": ["circuit breaker", "breaker", "protection", "motor protector", "motor starter"],
        "dept": "Electrical",
        "class_name": "Power Distribution",
        "fine": "Circuit Breakers",
    },
    {
        "keywords": ["contactor"],
        "desc_keywords": ["contactor", "magnetic contactor"],
        "dept": "Electrical",
        "class_name": "Motor Control",
        "fine": "Contactors",
    },
    {
        "keywords": ["sensor", "proximity"],
        "desc_keywords": ["sensor", "proximity", "photoelectric", "inductive"],
        "dept": "Automation",
        "class_name": "Sensors & Detectors",
        "fine": "Sensors",
    },
    {
        "keywords": ["plc", "programmable"],
        "desc_keywords": ["plc", "programmable logic controller", "controller"],
        "dept": "Automation",
        "class_name": "Controllers",
        "fine": "PLCs",
    },
    {
        "keywords": ["valve"],
        "desc_keywords": ["valve", "solenoid valve", "ball valve"],
        "dept": "Plumbing",
        "class_name": "Valves",
        "fine": "General Valves",
    },
    {
        "keywords": ["fittings", "fitting"],
        "desc_keywords": ["fitting", "fittings", "pipe fitting"],
        "dept": "Plumbing",
        "class_name": "Pipe & Tube Fittings",
        "fine": "General Fittings",
    },
    {
        "keywords": ["faucet"],
        "desc_keywords": ["faucet", "tap", "spout"],
        "dept": "Plumbing",
        "class_name": "Faucets & Parts",
        "fine": "Faucets",
    },
    {
        "keywords": ["motor"],
        "desc_keywords": ["motor", "induction motor", "servo motor", "electric motor"],
        "dept": "Electrical",
        "class_name": "Motors & Power Transmission",
        "fine": "Motors",
    },
    {
        "keywords": ["relay"],
        "desc_keywords": ["relay", "safety relay", "control relay"],
        "dept": "Electrical",
        "class_name": "Relays & Timers",
        "fine": "Relays",
    },
    {
        "keywords": ["connector", "terminal"],
        "desc_keywords": ["connector", "terminal", "terminal block"],
        "dept": "Electrical",
        "class_name": "Connectors & Terminals",
        "fine": "Connectors",
    },
]


class TaxonomyEngine:
    """
    Classifies products into Dept, Class, Fine, and Classpath.
    Uses keyword-based rules against category and description text.
    Returns structured TaxonomyResult with confidence and status.
    """

    def __init__(self, custom_rules: Optional[List[Dict]] = None):
        self.rules = custom_rules if custom_rules is not None else TAXONOMY_RULES

    def classify_product(
        self,
        category_hint: str,
        description: str,
        brand: str = "",
    ) -> TaxonomyResult:
        """
        Classify a product and return a structured TaxonomyResult.
        """
        hint = (category_hint or "").lower()
        desc = (description or "").lower()
        combined = f"{hint} {desc}"

        best_match = None
        best_score = 0

        for rule in self.rules:
            score = 0

            # Check category keywords (higher weight)
            for kw in rule["keywords"]:
                if kw in hint:
                    score += 3
                elif kw in desc:
                    score += 2

            # Check description keywords
            for kw in rule.get("desc_keywords", []):
                if kw in combined:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = rule

        if best_match is None or best_score == 0:
            # No match — return UNRESOLVED with the category hint as classpath
            return TaxonomyResult(
                dept="Unclassified",
                class_name="Unclassified",
                fine="Unclassified",
                classpath=category_hint or "Unclassified",
                confidence=0.0,
                status=TaxonomyStatus.UNRESOLVED,
            )

        dept = best_match["dept"]
        class_name = best_match["class_name"]
        fine = best_match["fine"]
        classpath = f"{dept} > {class_name} > {fine}"

        # Determine confidence based on match quality
        if best_score >= 4:
            confidence = 0.90
            status = TaxonomyStatus.RESOLVED
        elif best_score >= 1:
            confidence = 0.75
            if any(kw in hint for kw in best_match["keywords"]):
                status = TaxonomyStatus.RESOLVED
            else:
                status = TaxonomyStatus.HEURISTIC
        else:
            confidence = 0.50
            status = TaxonomyStatus.LOW_CONFIDENCE

        return TaxonomyResult(
            dept=dept,
            class_name=class_name,
            fine=fine,
            classpath=classpath,
            confidence=confidence,
            status=status,
        )


_default_engine: Optional[TaxonomyEngine] = None


def get_taxonomy_engine() -> TaxonomyEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = TaxonomyEngine()
    return _default_engine
