"""Prototype : relais des ressources non-infinies (§9.3).

Gère les recettes « relais » : pour chaque recette du début qui consommait
des ressources environnementales (arbres/rochers/poissons), une nouvelle
recette produit le même item avec uniquement des ressources durables, et
est dispatchée dans les 3 premières techs.

Configuration :
- prefix : préfixe des noms de recettes relais
- max_dispatch_steps : nombre max de techs de dispatch (les 3 premières)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.prototypes.base import PrototypeConfig


@dataclass
class RelayConfig(PrototypeConfig):
    """Configuration pour la phase relais (§9.3)."""
    prefix: str = "randputf-relay-"
    max_dispatch_steps: int = 3

    @classmethod
    def from_config(cls, config: dict) -> RelayConfig:
        cfg = config.get("relay", {})
        return cls(
            prefix=str(cfg.get("prefix", "randputf-relay-")),
            max_dispatch_steps=int(cfg.get("max_dispatch_steps", 3)),
        )