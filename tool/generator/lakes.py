"""Lacs de fluide (§7.5) : 3e type de RAW RESOURCE, après les items et les
fluides pumpjack.

Chaque lac est une tuile `randputf-lac-<fluid>` (copie de la tuile `water`
re-skinée) dont le champ `fluid` vaut le fluide tiré : une pompe offshore
vanilla posée dessus débite ce fluide, en volume INFINI comme l'eau. La
richesse ne règle que la TAILLE/densité du lac.

Comptage : la seed tire `count ∈ [min, max]` lacs (défaut min=1, soit totalement
comme les autres raws — zéro possible si l'on met min=0). Chaque lac reçoit un
fluide aléatoire du MÊME pool que les patchs fluides (tout fluide pipable) :
un fluide non tiré n'a AUCUN lac. Le mod SUPPRIME l'eau vanilla de la carte :
les seules nappes d'eau sont les lacs tirés (0 lac tiré = carte sans eau).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.common.db import VanillaDB

# Défauts config (settings.yaml section `lakes`).
DEFAULT_MIN = 1
DEFAULT_MAX = 3
DEFAULT_RICHNESS = (100000, 600000)


@dataclass
class Lake:
    resource: str  # nom du fluide
    richness: int  # richesse -> taille/densité du lac (volume = infini)

    def to_seed(self) -> dict:
        return {"resource": self.resource, "richness": self.richness}


def make_rng(seed_value: int) -> random.Random:
    # Flux indépendant des autres phases (patches, starter...) : ajouter des
    # lacs ne change PAS le tirage du reste de la seed.
    return random.Random(f"randputF:lakes:{seed_value}")


def pipable_lake_resources(db: VanillaDB) -> list[str]:
    """Pool des fluides pouvant devenir un LAC (extractibles sans électricité)."""
    return [f.name for f in db.pipable_fluids()]


def generate_lakes(rng: random.Random, db: VanillaDB, config: dict) -> list[Lake]:
    cfg = config.get("lakes", {})
    low = int(cfg.get("min", DEFAULT_MIN))
    high = int(cfg.get("max", DEFAULT_MAX))
    if low < 0:
        low = 0
    if high < low:
        high = low
    count = rng.randint(low, high)

    lo, hi = tuple(cfg.get("richness_fluid", list(DEFAULT_RICHNESS)))
    lo, hi = int(lo), int(hi)

    candidates = [(f.name, (lo, hi)) for f in db.pipable_fluids()]
    if not candidates or count == 0:
        return []

    # (A5) Échantillonnage SANS remise : au plus un lac par fluide. Si `count`
    # dépasse le nombre de fluides pipables, on plafonne au pool (aucun doublon).
    rng.shuffle(candidates)
    count = min(count, len(candidates))

    lakes = []
    for resource, (res_lo, res_hi) in candidates[:count]:
        lakes.append(Lake(resource, rng.randint(res_lo, res_hi)))
    return lakes