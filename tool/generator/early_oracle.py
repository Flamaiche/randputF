"""Oracle « early » — watershed obtenable sans électricité (bootstrap inline).

Redesign §10ter (correct-by-construction, plus de passe de rattrapage) :
plutôt que de casser après coup les recettes promises devenues profondes, on
contraint leur CRÉATION. L'oracle maintient incrémentalement le watershed
pré-électricité pendant la phase starter + électricité :

- initialisé depuis les sources dès le départ : environnement (bois/pierre/
  poisson), patchs items (minables par foreuse non-électrique) et lacs
  (fluides pompés par pompe offshore, sans électricité) ;
- le kit du spawn est volontairement exclu : stock fini de crash, pas une
  matière première re-fabriquable ;
- chaque recette créée pendant le mode « early » étend le watershed si son
  atelier est non-électrique (handcraft / burner).

Quand le mode « early » est actif, ``recipes._make_recipe`` tire les
ingrédients uniquement dans ce watershed et n'accepte que des ateliers
non-électriques → toute recette promise du starter est jouable pré-électricité
par construction. La contrainte NET≤0 / SCC n'est plus qu'un diagnostic
(``find_cycles``) : seule l'atteignabilité pré-élec compte.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM, VanillaDB


def build_early_sources(
    db: VanillaDB,
    patch_resources: set[str],
    lake_resources: set[str],
) -> tuple[set[str], set[str]]:
    """Ressources obtenables dès le départ, sans électricité ni craft.

    - environnement : bois/pierre/poisson (main) ;
    - patchs items : minables par foreuse non-électrique (jamais un patch
      fluide — pumpjack électrique) ;
    - lacs : fluides pompés par pompe offshore (void).

    Retourne ``(items, fluides)``."""
    items = set(ENVIRONMENTAL_ITEMS) & set(db.items)
    items |= set(patch_resources)
    fluids: set[str] = set(lake_resources)
    return items, fluids


def is_electric_crafter(db: VanillaDB, recipe: dict) -> bool:
    """La recette est-elle craftée dans un bâtiment électrique ? Sans atelier
    (bootstrap) → False. Atelier burner/void/heat → False. Bâtiment inconnu :
    indulgence (on ne bloque pas sur un bâtiment qu'on ne connaît pas)."""
    crafted_in = recipe.get("crafted_in")
    if not crafted_in:
        return False
    building = db.buildings.get(crafted_in)
    return building is not None and building.energy_type == "electric"


@dataclass
class EarlyOracle:
    """Watershed pré-électricité courant, maintenu pendant le bootstrap.

    ``active`` : tant que starter + électricité n'ont pas fini (gel des
    promesses, pipeline.py), les recettes sont tirées uniquement dans
    ``items``/``fluids`` et sans atelier électrique ; chaque recette
    non-électrique ajoute son produit au watershed.
    """

    items: set[str] = field(default_factory=set)
    fluids: set[str] = field(default_factory=set)
    active: bool = False

    def activate(self, items: set[str], fluids: set[str]) -> None:
        self.items = set(items)
        self.fluids = set(fluids)
        self.active = True

    def deactivate(self) -> None:
        self.active = False

    def add_sources(self, items: set[str] | None = None, fluids: set[str] | None = None) -> None:
        """Étend les sources après coup (patches/lacs réparateurs ajoutés par
        l'électricité) : leurs ressources sont obtenables sans électricité."""
        if items:
            self.items |= items
        if fluids:
            self.fluids |= fluids

    def extend(self, db: VanillaDB, recipe: dict) -> None:
        """Une recette non-électrique ajoute ses produits au watershed."""
        if not self.active or is_electric_crafter(db, recipe):
            return
        for res in recipe.get("results", []):
            bucket = self.items if res["type"] == SLOT_ITEM else self.fluids
            bucket.add(res["name"])

    def pool(self) -> list[tuple[str, str]]:
        return [(SLOT_ITEM, n) for n in sorted(self.items)] + [
            (SLOT_FLUID, n) for n in sorted(self.fluids)
        ]

    def in_watershed(self, kind: str, name: str) -> bool:
        return name in (self.items if kind == SLOT_ITEM else self.fluids)


def compute_early_reachable(
    db: VanillaDB,
    recipes: list[dict],
    item_sources: set[str],
    fluid_sources: set[str],
) -> tuple[set[str], set[str]]:
    """Watershed des produits obtenables SANS électricité (clôture transitive)
    sur un ensemble complet de recettes (diagnostic/validation finale).

    Une recette est exécutable pré-électricité ssi son atelier n'est pas
    électrique ET tous ses ingrédients (items/fluides) sont dans le watershed.
    Retourne ``(items, fluides)`` atteignables depuis les sources."""
    items = set(item_sources)
    fluids = set(fluid_sources)
    changed = True
    while changed:
        changed = False
        for recipe in recipes:
            if is_electric_crafter(db, recipe):
                continue
            ok = True
            for ing in recipe.get("ingredients", []):
                bucket = items if ing["type"] == SLOT_ITEM else fluids
                if ing["name"] not in bucket:
                    ok = False
                    break
            if not ok:
                continue
            for res in recipe.get("results", []):
                bucket = items if res["type"] == SLOT_ITEM else fluids
                if res["name"] not in bucket:
                    bucket.add(res["name"])
                    changed = True
    return items, fluids