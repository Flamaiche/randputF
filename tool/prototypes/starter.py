"""Configuration : kit de départ, extraction et transformation (§7 et §8).

Configuration lue par le générateur starter_chain :
- nombre de munitions du kit
- probabilité d'inclure un inserter
- patterns de transport par rôle
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.prototypes.base import PrototypeConfig


@dataclass
class StarterConfig(PrototypeConfig):
    """Configuration pour le kit de départ et la chaîne initiale."""
    # Kit
    ammo_count: int = 50
    # Transports
    inserter_chance: float = 0.5
    # Patterns de recherche d'items de transport par rôle
    transport_patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "belt": ["transport-belt"],
        "splitter": ["splitter"],
        "underground": ["underground-belt"],
        "pipe": ["pipe"],
        "pipe_to_ground": ["pipe-to-ground"],
        "inserter": ["inserter"],
    })

    @classmethod
    def from_config(cls, config: dict) -> StarterConfig:
        starter_cfg = config.get("starter", {})
        return cls(
            ammo_count=int(starter_cfg.get("ammo_count", 50)),
            inserter_chance=float(starter_cfg.get("inserter_chance", 0.5)),
        )