"""Banned Ingredients Filter for First Club.

Maintains a blocklist of ingredients that First Club does not allow in
any product sold on the platform. Products containing banned ingredients
are flagged during onboarding and excluded from the active catalog.

The list is curated based on First Club's published banned ingredients
policy (https://www.firstclub.site/banned-ingredients).
"""

from __future__ import annotations

# ── First Club Banned Ingredients ─────────────────────────────────────
# Sourced from First Club's public banned ingredients page.
# All comparisons are case-insensitive and use substring matching.

BANNED_INGREDIENTS: set[str] = {
    # Artificial Colors / Dyes
    "tartrazine", "sunset yellow", "allura red", "brilliant blue",
    "indigo carmine", "erythrosine", "fast green", "fd&c",
    "artificial color", "artificial colour", "synthetic color",
    "synthetic colour", "caramel color (class iii)", "caramel color (class iv)",

    # Artificial Preservatives
    "sodium benzoate", "potassium sorbate", "potassium benzoate",
    "sodium nitrite", "sodium nitrate", "bha", "bht",
    "butylated hydroxyanisole", "butylated hydroxytoluene",
    "tbhq", "tert-butylhydroquinone", "calcium propionate",
    "sulfur dioxide", "sodium bisulfite", "sodium metabisulfite",

    # Artificial Sweeteners
    "aspartame", "sucralose", "acesulfame potassium", "acesulfame-k",
    "saccharin", "neotame", "advantame",
    "artificial sweetener", "sugar alcohol",

    # Artificial Flavors
    "artificial flavor", "artificial flavour",
    "nature-identical flavor", "nature identical flavour",

    # Harmful Fats
    "trans fat", "partially hydrogenated",
    "hydrogenated vegetable oil", "hydrogenated palm oil",
    "interesterified fat", "margarine",

    # MSG & Flavor Enhancers
    "monosodium glutamate", "msg", "disodium guanylate",
    "disodium inosinate", "yeast extract",
    "hydrolyzed vegetable protein", "hydrolyzed soy protein",

    # High Fructose Corn Syrup
    "high fructose corn syrup", "hfcs", "corn syrup",
    "glucose-fructose syrup", "isoglucose",

    # Emulsifiers / Stabilizers (controversial)
    "carrageenan", "polysorbate 80", "polysorbate 60",
    "sodium stearoyl lactylate", "datem",
    "calcium stearoyl-2-lactylate",

    # Bleaching & Processing Agents
    "potassium bromate", "azodicarbonamide",
    "chlorine dioxide", "benzoyl peroxide",

    # Pesticide Residues / Contaminants (flagged by presence)
    "brominated vegetable oil", "bvo",

    # Other
    "titanium dioxide", "propylparaben", "methylparaben",
    "sodium aluminum phosphate", "aluminum",
}


def check_ingredients(ingredient_list: list[str]) -> list[str]:
    """Check a list of ingredients against the banned list.

    Returns a list of banned ingredients found (case-insensitive
    substring match).  Empty list means the product is clean.
    """
    found: list[str] = []
    for ingredient in ingredient_list:
        ing_lower = ingredient.strip().lower()
        for banned in BANNED_INGREDIENTS:
            if banned in ing_lower or ing_lower in banned:
                found.append(ingredient.strip())
                break
    return found


def is_product_clean(ingredient_list: list[str]) -> bool:
    """Return True if no banned ingredients are found."""
    return len(check_ingredients(ingredient_list)) == 0


def get_banned_list() -> list[str]:
    """Return the full banned ingredients list, sorted alphabetically."""
    return sorted(BANNED_INGREDIENTS)
