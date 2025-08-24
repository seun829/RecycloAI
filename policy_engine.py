# policy_engine.py
from rules import RULES

PRIORITY_ATTRS = ["soft_bag", "foam", "paper_cup_or_carton", "greasy_or_wet", "hazard"]
ATTR_LABELS = {
    "soft_bag": "Soft bag / plastic wrap",
    "foam": "Foam / Styrofoam",
    "paper_cup_or_carton": "Paper cup or carton",
    "greasy_or_wet": "Greasy or wet",
    "hazard": "Hazardous item",
}

def _normalize_city(city: str | None) -> str:
    if not city:
        return "default"
    city = city.strip().lower()
    if "," in city:
        city = city.split(",", 1)[0].strip()
    return city or "default"

def _title_city(city_key: str) -> str:
    if city_key in ("default", "", None):
        return "Default"
    # Title-case each word (keep 'san'/'los' properly capitalized)
    return " ".join(w.capitalize() for w in city_key.split())

def decide_action(material: str, attrs: dict | None, city: str | None):
    attrs = attrs or {}
    city_key = _normalize_city(city)
    table = RULES.get(city_key, RULES["default"])
    mat_rules = table.get(material, RULES["default"].get(material, {"default": "Landfill"}))
    city_disp = _title_city(city_key)

    # attribute-specific overrides (priority order)
    for a in PRIORITY_ATTRS:
        if attrs.get(a) and a in mat_rules:
            attr_label = ATTR_LABELS.get(a, a.replace("_", " "))
            action = mat_rules[a]
            return action, f"{material} marked as '{attr_label}' → {action} ({city_disp})"

    # fallback to material default
    action = mat_rules.get("default", "Landfill")
    return action, f"{material} → {action} ({city_disp})"
