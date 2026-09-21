"""Configuration : kit de départ, extraction et transformation.

- nombre de munitions du kit
- probabilité d'inclure un inserter
- patterns de transport par rôle
"""

from __future__ import annotations

from dataclasses import dataclass

from tool.prototypes.base import PrototypeConfig


@dataclass
class StarterConfig(PrototypeConfig):
    """Configuration pour le kit de départ et la chaîne initiale."""
    # Kit
    ammo_count: int = 50
    # Transports
    inserter_chance: float = 0.5

    @classmethod
    def from_config(cls, config: dict) -> StarterConfig:
        starter_cfg = config.get("starter", {})
        return cls(
            ammo_count=int(starter_cfg.get("ammo_count", 50)),
            inserter_chance=float(starter_cfg.get("inserter_chance", 0.5)),
        )