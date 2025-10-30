# policy_engine.py
from misc.rules import RULES

PRIORITY_ATTRS = ["soft_bag", "foam", "paper_cup", "carton", "greasy_or_wet", "hazard"]
ATTR_LABELS = {
    "soft_bag": "Soft bag / plastic wrap",
    "foam": "Foam / Styrofoam",
    "paper_cup": "Paper cup",
    "carton": "Carton",
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
    return " ".join(w.capitalize() for w in city_key.split())


def _normalize_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off", ""}:
        return False
    return True  # any other non-empty string


def _normalize_attrs(attrs: dict | None) -> dict:
    attrs = attrs or {}
    return {k: _normalize_bool(v) for k, v in attrs.items()}


def _material_key_case_insensitive(table: dict, material: str | None) -> str | None:
    """
    Return the correct material key from `table` using robust case handling.
    Tries:
      1) exact
      2) Title Case (e.g., "plastic bottle" -> "Plastic Bottle")
      3) case-insensitive scan over existing keys
    """
    if not material:
        return None
    m = material.strip()
    if not m:
        return None

    # 1) exact
    if m in table:
        return m

    # 2) title-case
    m_title = " ".join(w.capitalize() for w in m.split())
    if m_title in table:
        return m_title

    # 3) case-insensitive scan
    m_lower = m.lower()
    for k in table.keys():
        if k.lower() == m_lower:
            return k

    return None


def _lookup_material_rules(city_key: str, material: str | None) -> tuple[dict, str]:
    """
    Resolve the material rules for a city with case-insensitive matching.
    Fallback order:
      1) City table match
      2) City's "Trash"
      3) Default table match
      4) Default "Trash"
      5) {"default": "Landfill"}
    Returns (rules_dict, resolved_material_name)
    """
    city_table = RULES.get(city_key, RULES["default"])

    key = _material_key_case_insensitive(city_table, material)
    if key:
        return city_table[key], key

    if "Trash" in city_table:
        return city_table["Trash"], "Trash"

    default_table = RULES["default"]
    key = _material_key_case_insensitive(default_table, material)
    if key:
        return default_table[key], key

    if "Trash" in default_table:
        return default_table["Trash"], "Trash"

    return {"default": "Landfill"}, material or "Unknown"


def decide_action(material: str, attrs: dict | None, city: str | None):
    """
    Decide action using case-insensitive material matching and boolean-normalized attrs.
    """
    city_key = _normalize_city(city)
    city_disp = _title_city(city_key)
    norm_attrs = _normalize_attrs(attrs)

    mat_rules, resolved_mat = _lookup_material_rules(city_key, material)

    # attribute-specific overrides (priority order)
    for a in PRIORITY_ATTRS:
        if norm_attrs.get(a) and a in mat_rules:
            attr_label = ATTR_LABELS.get(a, a.replace("_", " "))
            action = mat_rules[a]
            return action, f"{resolved_mat} marked as '{attr_label}' → {action} ({city_disp})"

    # fallback to material default
    action = mat_rules.get("default", "Landfill")
    return action, f"{resolved_mat} → {action} ({city_disp})"
