"""Phase endgame : chaîne de la fusée intable (gagnable).

La victoire passe par le rocket-silo : on y construit des ``rocket-part``
(recette vanilla EXEMPTE dans data-final-fixes, jamais désactivée). Mais ses
3 ingrédients (processing-unit, low-density-structure, rocket-fuel) ont leurs
recettes vanilla désactivées sans une recette générée — sinon ``rocket-part``
est incraftable et la partie ne finit pas (en 2.0, ``rocket-part`` ne consomme
que ces 3 items ; satellite reste optionnel).

Cette phase tourne APRÈS le récursif, AVANT la phase relais :
- garantit une recette générée pour chacun des 3 ingrédients (items existants
  du pool réutilisés, pas de doublon) ;
- ingrédients tirés dans le pool FINAL en interdisant les environnementaux
  (pas de fusée au bois/pierre/poisson, et surtout pas de relais de fusée
  tirés du pool de départ) ;
- retourne UNE tech macro-step de fin d'arbre qui unlocke ces recettes.

Anti-filière : ateliers de craft du pool profond (AM3, oil-refinery, ...),
tous déblocables avant cette tech finale.
"""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, ROCKET_CHAIN, SLOT_ITEM, VanillaDB
from tool.generator.recipes import ProgressionState, ensure_obtainable


def ensure_rocket_chain(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> list[dict]:
    """Garantit les recettes de la chaîne fusée et retourne la tech de fin
    d'arbre qui les unlocke (une seule, en dernière position).

    Outre les 3 ingrédients de ``rocket-part``, garanti aussi le rocket-silo
    LUI-MÊME : la victoire passe par y crafter ``rocket-part`` ; si la
    récursion s'arrête avant de déployer le silo, aucune seed ne finirait.
    Les 4 recettes sont unlockées par ``randputf-endgame-rocket``."""
    targets = sorted(ROCKET_CHAIN)
    silo = db.items.get("rocket-silo")
    if silo is not None and silo.place_result in db.buildings:
        targets.append("rocket-silo")
    for item in targets:
        ensure_obtainable(
            rng,
            db,
            state,
            SLOT_ITEM,
            item,
            forbidden=frozenset(ENVIRONMENTAL_ITEMS),
        )
    recipe_names: list[str] = []
    for item in targets:
        for recipe in state.recipes:
            if any(
                res.get("type") == SLOT_ITEM and res.get("name") == item
                for res in recipe.get("results", [])
            ):
                if recipe["name"] not in recipe_names:
                    recipe_names.append(recipe["name"])
                break
    if not recipe_names:
        return []
    return [
        {
            "id": "randputf-endgame-rocket",
            "title": "Assemblage de la fusée",
            "unlocks_recipes": recipe_names,
            "unlocks_buildings": [],
            "cost": [],
            "count": 1,
        }
    ]