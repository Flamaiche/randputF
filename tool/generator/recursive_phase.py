"""Phase 3 : récursion pondérée (README §9).

NOT_IMPLEMENTED : logique à écrire ensemble.

Contrats :
- expand_recursive(rng, db, patches, starter) remplit l'état global :
  tirages ponderes par pourcentage d'obtention dependant du type de bâtiment
  et du nombre total de bâtiments deja debloques ; science packs inclus dans
  les memes tirages ; plus on avance, plus le pool s'elargit.
- Chaque recette est generee depuis le pool atteignable croise avec les
  bâtiments capables de la produire (types, slots, directives).
- Deblocage sur le tas (§9.3) : ressource brute inconnue integree
  immediatement ; ressource non automatisable -> sa facon de s'obtenir
  debloquee au meme moment ; tout prerequis manquant genere son craft sur
  place.
- recipes_to_seed() / steps() restituent l'etat sous forme seed.
"""

from __future__ import annotations

import random

from tool.common.db import VanillaDB
from tool.generator.map_patches import Patch
from tool.generator.starter_chain import StarterChain

_state = {"recipes": [], "steps": []}


def expand_recursive(
    rng: random.Random,
    db: VanillaDB,
    patches: list[Patch],
    starter: StarterChain,
) -> None:
    """A implémenter à deux : remplir _state avec recettes et étapes."""
    del rng, db, patches, starter


def steps() -> list[dict]:
    return _state["steps"]


def recipes_to_seed() -> list[dict]:
    return _state["recipes"]
