# rules.py
# Attributes (plain): soft_bag, foam, paper_cup_or_carton, greasy_or_wet
# City keys are case-insensitive; unknown cities fall back to "default".

RULES = {
    "default": {
        # Plastics
        # - soft_bag: plastic bags/wrap (scrunchable) → Drop-off
        # - foam: Styrofoam/expanded polystyrene → Landfill
        # - rigid containers → Recyclable
        "Plastic": {
            "soft_bag": "Drop-off",
            "foam": "Landfill",
            "default": "Recyclable",
        },

        # Paper & cardboard
        # - greasy_or_wet: oily/soiled pizza boxes, wet cardboard → Landfill
        # - paper_cup_or_carton: lined cups/cartons → Landfill
        "Paper": {
            "greasy_or_wet": "Landfill",
            "paper_cup_or_carton": "Landfill",
            "default": "Recyclable",
        },
        "Cardboard": {
            "greasy_or_wet": "Landfill",
            "default": "Recyclable",
        },

        # Metals & glass widely recyclable
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},

        # Catch-all
        "Trash": {"default": "Landfill"},
    },

    # --- Cities with curbside organics/compost (greasy paper → Compost) ---
    "austin": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "san francisco": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "seattle": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "portland": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "san jose": {  # compost/organics accepted
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "denver": {   # curbside compost available in many areas
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },

    # --- Big cities (no universal curbside compost) → conservative on greasy paper ---
    "new york": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "los angeles": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Compost", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Compost", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "chicago": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "boston": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "philadelphia": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "houston": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "miami": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "phoenix": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "washington": {  # Washington, DC
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "atlanta": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
    "minneapolis": {
        "Plastic": {"soft_bag": "Drop-off", "foam": "Landfill", "default": "Recyclable"},
        "Paper": {"greasy_or_wet": "Landfill", "paper_cup_or_carton": "Landfill", "default": "Recyclable"},
        "Cardboard": {"greasy_or_wet": "Landfill", "default": "Recyclable"},
        "Metal": {"default": "Recyclable"},
        "Glass": {"default": "Recyclable"},
        "Trash": {"default": "Landfill"},
    },
}
