"""Prototype : relais des ressources non-infinies.

Pour chaque recette du début consommant des ressources environnementales
(arbres/rochers/poissons), une recette relais produit le même item avec
uniquement des ressources durables, dispatchée dans les 3 premières techs.

- prefix : préfixe des noms de recettes relais
- max_dispatch_steps : nombre max de techs de dispatch
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class RelayConfig(PrototypeConfig):
    """Réglages de la phase relais (recettes de dispatch intermédiaires).

    ``prefix`` préfixe les noms générés et ``max_dispatch_steps`` borne le
    nombre d'étapes de dispatch par chaîne. Les valeurs par défaut sont lues
    depuis ``config/defaults.yaml`` via ``from_config``.
    """
    prefix: str = "randputf-relay-"
    max_dispatch_steps: int = 3

    @classmethod
    def from_config(cls, config: dict) -> RelayConfig:
        """Construit la configuration ``relay`` depuis le dict complet.

        ``config`` peut être partiel ; les clés absentes prennent les défauts de ``defaults.yaml``. Retourne une ``RelayConfig`` validée.
        """
        cfg = config.get("relay", {})
        return cls(
            prefix=str(cfg.get("prefix", _cfg.default_value("relay", "prefix"))),
            max_dispatch_steps=int(cfg.get("max_dispatch_steps", _cfg.default_value("relay", "max_dispatch_steps"))),
        )