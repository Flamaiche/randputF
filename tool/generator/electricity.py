"""Phase 4 : électricité (README §10).

NOT_IMPLEMENTED : logique à écrire ensemble.

Contrat :
- resolve_electricity(rng, db, starter) : si un bâtiment tiré demande de
  l'energie, un générateur est choisi aléatoirement ; la suite est decidée
  après que tout le reste est posé.
- Combustible du générateur : item combustible assigné depuis le pool ;
  sinon fluide combustible disponible ; sinon recette créée avec tout ce qui
  va avec (déblocage sur le tas).
- L'énergie reste un réseau vanilla : elle n'est jamais randputisée.
"""

from __future__ import annotations

import random

from tool.common.db import VanillaDB
from tool.generator.starter_chain import StarterChain


def resolve_electricity(rng: random.Random, db: VanillaDB, starter: StarterChain) -> None:
    """A implémenter à deux : générateur à la demande + combustible résolu."""
    del rng, db, starter
