"""Arbre technologique linéaire valide (README §13).

IMPLEMENTE generiquement. Chaque etape produite par les phases devient une
technologie ; les prerequis suivent strictement l'ordre du graphe (aucune
boucle). Le branchement en arbres est explicitement hors scope v1.
"""

from __future__ import annotations


def build_linear_tech_tree(steps: list[dict]) -> list[dict]:
    technologies = []
    previous_id = None
    for index, step in enumerate(steps):
        tech_id = step.get("id") or f"randputf-step-{index}"
        unit_ingredients = [
            {"name": ing["name"], "type": ing.get("type", "item"), "amount": int(ing["amount"])}
            for ing in step.get("cost", [])
        ]
        effects = [{"type": "unlock-recipe", "recipe": r} for r in step.get("unlocks_recipes", [])]
        for building in step.get("unlocks_buildings", []):
            effects.append({"type": "unlock-recipe", "recipe": building})
        
        count = int(step.get("count", 10))
        if count <= 0:
            count = 1
            
        tech = {
            "id": tech_id,
            "localised_name": step.get("title") or tech_id,
            "prerequisites": [previous_id] if previous_id else [],
            "unit": {"count": count, "ingredients": unit_ingredients},
            "effects": effects,
        }
        technologies.append(tech)
        previous_id = tech_id
    return technologies
