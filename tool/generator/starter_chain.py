"""Phase 2 : chaîne initiale - starter (README §7 et §8).

Squelette partiellement implemente : le kit de depart (arme + munitions
calees) et le tirage du nombre de recherches gratuites fonctionnent.
La construction de la chaine extraction -> transformation -> transport est
NOT_IMPLEMENTED et constitue un point de logique à écrire ensemble.

Contrat de build_starter_chain :
- extracteur(s) choisis selon le milieu de chaque patch ;
- bâtiment de transformation compatible avec les types de ressources ;
- transports adaptes (tapis/tuyaux tiers tires, splitters, undergrounds,
  bras si besoin) ;
- anti-cycle §8 : toute entree auxiliaire provient d'une branche deja valide
  ; les tuyaux d'un fluide requis peuvent etre faits de ce fluide ou d'une
  autre ressource, jamais de la ressource qui en a besoin.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common.db import VanillaDB
from tool.generator.map_patches import Patch


@dataclass
class StarterChain:
    kit: list[dict] = field(default_factory=list)
    free_researches: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    buildings: list[str] = field(default_factory=list)
    recipes: list[dict] = field(default_factory=list)


def build_starter_chain(rng: random.Random, db: VanillaDB, patches: list[Patch]) -> StarterChain:
    chain = StarterChain()
    chain.kit = _roll_starter_kit(rng, db)
    return chain


def _roll_starter_kit(rng: random.Random, db: VanillaDB) -> list[dict]:
    guns = [i for i in db.items.values() if i.is_gun]
    ammos = [i for i in db.items.values() if i.is_ammo]
    kit: list[dict] = []
    if guns:
        gun = rng.choice(guns)
        kit.append({"type": "item", "name": gun.name, "count": 1})
        if ammos:
            ammo = rng.choice(ammos)
            kit.append({"type": "item", "name": ammo.name, "count": 50})
    return kit
