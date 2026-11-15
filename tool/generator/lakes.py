"""Lacs de fluide (§7.5) : 3e type de raw resource, après les items et les
fluides à pumpjack.

Chaque lac est une tuile `randputf-lac-<fluid>` (copie de `water` re-skinée)
dont le champ `fluid` vaut le fluide tiré : une pompe offshore vanilla posée
dessus débite ce fluide, en volume INFINI comme l'eau. La richesse ne règle
que la taille/densité du lac. La seed tire `count ∈ [min, max]` lacs ; chaque
lac reçoit un fluide du même pool que les patchs fluides. Le mod SUPPRIME
l'eau vanilla : les seules nappes d'eau sont les lacs tirés (0 lac = carte
sans eau).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.common.db import VanillaDB
from tool.common import config as _cfg
from tool.common.rng import make_seeded_rng

# Valeurs dans ``config/defaults.yaml`` (section ``lakes``) : min=1, max=3,
# richness_fluid=[100000, 600000].


@dataclass
class Lake:
    """Lac de fluide posé sur la carte.

    ``resource`` est le nom du fluide et ``richness`` sa taille/densité (le volume est infini). Sert à la sérialisation dans ``seed[\"lakes\"]`` et au rejoueur.
    """
    resource: str  # fluide
    richness: int  # taille/densité du lac (volume = infini)

    def to_seed(self) -> dict:
        """Retourne la forme sérialisée d'un lac.

        Le résultat est un dict ``{\"resource\": ..., \"richness\": ...}`` directement inséré dans la seed. Ne mute pas l'objet.
        """
        return {"resource": self.resource, "richness": self.richness}


def make_rng(seed_value: int) -> random.Random:
    """Crée le flux RNG dédié aux lacs.

    ``seed_value`` est la graine de la seed ; le sel distinct garantit qu'ajouter des lacs ne change pas les autres tirages. Retourne un ``random.Random``.
    """
    return make_seeded_rng(seed_value, "randputF:lakes:")


def pipable_lake_resources(db: VanillaDB) -> list[str]:
    """Retourne les fluides pouvant devenir un lac.

    ``db`` fournit les fluides pipables du dump. Le résultat est la liste triée de leurs noms ; aucun filtrage par électricité n'est fait ici.
    """
    return [f.name for f in db.pipable_fluids()]


def generate_lakes(rng: random.Random, db: VanillaDB, config: dict) -> list[Lake]:
    """Tire les lacs de la seed : nombre (bornes config ``lakes.min/max``),
    ressource (au plus un lac par fluide pipable, sans remise) et richesse
    (bornes ``richness_fluid``)."""
    cfg = config.get("lakes", {})
    low = int(cfg.get("min", _cfg.default_value("lakes", "min")))
    high = int(cfg.get("max", _cfg.default_value("lakes", "max")))
    if low < 0:
        low = 0
    if high < low:
        high = low
    count = rng.randint(low, high)

    lo, hi = tuple(cfg.get("richness_fluid", _cfg.default_value("lakes", "richness_fluid")))
    lo, hi = int(lo), int(hi)

    candidates = [(f.name, (lo, hi)) for f in db.pipable_fluids()]
    if not candidates or count == 0:
        return []

    # (A5) SANS remise : au plus un lac par fluide (plafond au pool).
    rng.shuffle(candidates)
    count = min(count, len(candidates))

    lakes = []
    for resource, (res_lo, res_hi) in candidates[:count]:
        lakes.append(Lake(resource, rng.randint(res_lo, res_hi)))
    return lakes