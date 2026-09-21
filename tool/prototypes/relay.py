"""Prototype : relais des ressources non-infinies.

Pour chaque recette du début consommant des ressources environnementales
(arbres/rochers/poissons), une recette relais produit le même item avec
uniquement des ressources durables, dispatchée dans les 3 premières techs.

- prefix : préfixe des noms de recettes relais
- max_dispatch_steps : nombre max de techs de dispatch
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.prototypes.base import PrototypeConfig


@dataclass
class RelayConfig(PrototypeConfig):
    """Configuration pour la phase relais."""
    prefix: str = "randputf-relay-"
    max_dispatch_steps: int = 3

    @classmethod
    def from_config(cls, config: dict) -> RelayConfig:
        cfg = config.get("relay", {})
        return cls(
            prefix=str(cfg.get("prefix", "randputf-relay-")),
            max_dispatch_steps=int(cfg.get("max_dispatch_steps", 3)),
        )